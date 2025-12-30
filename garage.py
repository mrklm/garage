#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garage — v4.1.4 (clean, single-file)

DB attendue : garage.db (à côté du script)
Dossier photos : ./assets (à côté du script)

Fonctions :
- Flotte de véhicules (CRUD + photo PNG copiée dans ./assets)
- Pleins (CRUD + autocomplétion Lieu)
- Entretiens (types + CRUD)
- Onglet Général : 2 véhicules par page, conso moyenne, état batterie, coût estimé, rappels filtrés (uniquement cochés)

Compat :
- Tkinter standard
- SQLite
- Python 3.10+ (OK 3.13)
"""
from __future__ import annotations

import os
import re
import sqlite3
import shutil
import uuid
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date

APP_TITLE = "Garage v4.1.4"
DB_FILE = os.path.join(os.path.dirname(__file__), "garage.db")
ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets")


# ----------------- Helpers -----------------

def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _columns(cur: sqlite3.Cursor, table: str) -> set[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return {r["name"] for r in cur.fetchall()}


def _table_exists(cur: sqlite3.Cursor, table: str) -> bool:
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1", (table,))
    return cur.fetchone() is not None


def _ensure_schema():
    """
    Crée les tables minimum si elles n'existent pas (ne détruit rien),
    puis applique des migrations légères idempotentes.
    """
    conn = _connect_db()
    cur = conn.cursor()

    # Tables minimales
    if not _table_exists(cur, "
    "):
        cur.execute("""
            CREATE TABLE vehicules(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT,
                marque TEXT,
                modele TEXT,
                motorisation TEXT,
                energie TEXT,
                annee INTEGER,
                immatriculation TEXT,
                photo_file TEXT
            )
        """)

    if not _table_exists(cur, "pleins"):
        cur.execute("""
            CREATE TABLE pleins(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicule_id INTEGER NOT NULL,
                date_iso TEXT,
                km INTEGER,
                litres REAL,
                prix_litre REAL,
                total REAL,
                lieu TEXT,
                FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE
            )
        """)

    if not _table_exists(cur, "entretien_types"):
        cur.execute("""
            CREATE TABLE entretien_types(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nom TEXT NOT NULL,
                owner_vehicle_id INTEGER,
                period_km INTEGER,
                period_months INTEGER,
                is_active INTEGER DEFAULT 1,
                FOREIGN KEY(owner_vehicle_id) REFERENCES vehicules(id) ON DELETE SET NULL
            )
        """)

    if not _table_exists(cur, "vehicule_entretien_types"):
        cur.execute("""
            CREATE TABLE vehicule_entretien_types(
                vehicule_id INTEGER NOT NULL,
                type_id INTEGER NOT NULL,
                enabled INTEGER DEFAULT 1,
                PRIMARY KEY(vehicule_id, type_id),
                FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE,
                FOREIGN KEY(type_id) REFERENCES entretien_types(id) ON DELETE CASCADE
            )
        """)

    if not _table_exists(cur, "entretiens"):
        cur.execute("""
            CREATE TABLE entretiens(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vehicule_id INTEGER NOT NULL,
                type_id INTEGER,
                intervention TEXT,
                date_iso TEXT,
                km INTEGER,
                cout REAL,
                details TEXT,
                kind TEXT,
                performed_by TEXT,
                battery_voltage REAL,
                FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE,
                FOREIGN KEY(type_id) REFERENCES entretien_types(id) ON DELETE SET NULL
            )
        """)

    # Migrations idempotentes (colonnes ajoutées si manquantes)
    try:
        cols_t = _columns(cur, "entretien_types")
        if "period_months" not in cols_t:
            cur.execute("ALTER TABLE entretien_types ADD COLUMN period_months INTEGER")
    except Exception:
        pass

    try:
        cols_e = _columns(cur, "entretiens")
        if "kind" not in cols_e:
            cur.execute("ALTER TABLE entretiens ADD COLUMN kind TEXT")
        if "performed_by" not in cols_e:
            cur.execute("ALTER TABLE entretiens ADD COLUMN performed_by TEXT")
        if "battery_voltage" not in cols_e:
            cur.execute("ALTER TABLE entretiens ADD COLUMN battery_voltage REAL")
    except Exception:
        pass

    try:
        cols_v = _columns(cur, "vehicules")
        if "photo_file" not in cols_v:
            cur.execute("ALTER TABLE vehicules ADD COLUMN photo_file TEXT")
    except Exception:
        pass

    try:
        cols_vtt = _columns(cur, "vehicule_entretien_types")
        if "enabled" not in cols_vtt:
            cur.execute("ALTER TABLE vehicule_entretien_types ADD COLUMN enabled INTEGER DEFAULT 1")
            cur.execute("UPDATE vehicule_entretien_types SET enabled=1 WHERE enabled IS NULL")
    except Exception:
        pass

    # preconisations constructeur (notes libres par véhicule)
    cur.execute("""CREATE TABLE IF NOT EXISTS preconisations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicule_id INTEGER NOT NULL,
            texte TEXT NOT NULL,
            created_at TEXT,
            FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE CASCADE
        )""")


    conn.commit()
    conn.close()


def _ensure_assets_dir():
    os.makedirs(ASSETS_DIR, exist_ok=True)


def _copy_vehicle_photo(src_path: str, vehicle_id: int | None = None) -> str | None:
    """Copie un PNG dans ./assets et retourne le nom de fichier stocké en DB."""
    if not src_path:
        return None
    _ensure_assets_dir()
    base = os.path.basename(src_path)
    name, ext = os.path.splitext(base)
    if ext.lower() != ".png":
        raise ValueError("La photo doit être un fichier .PNG")

    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", name).strip("_") or "vehicule"
    tag = f"v{int(vehicle_id)}_" if vehicle_id else ""
    out_name = f"{tag}{safe}_{uuid.uuid4().hex[:8]}.png"
    dst = os.path.join(ASSETS_DIR, out_name)
    shutil.copy2(src_path, dst)
    return out_name


def _load_vehicle_photo_tk(photo_file: str | None, max_w=360, max_h=220):
    """Charge un PNG via PhotoImage et le réduit (subsample) pour l'affichage."""
    if not photo_file:
        return None
    path = os.path.join(ASSETS_DIR, photo_file)
    if not os.path.exists(path):
        return None
    try:
        img = tk.PhotoImage(file=path)
    except Exception:
        return None

    try:
        w, h = img.width(), img.height()
        sx = max(1, int(w / max_w))
        sy = max(1, int(h / max_h))
        s = max(sx, sy)
        if s > 1:
            img = img.subsample(s, s)
    except Exception:
        pass
    return img


def _parse_iso_date(value):
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        s = s.split("T")[0].split(" ")[0]
        try:
            return datetime.strptime(s, "%Y-%m-%d").date()
        except Exception:
            return None
    return None


def _fmt_date(d) -> str:
    dd = _parse_iso_date(d)
    return dd.strftime("%d/%m/%Y") if dd else ""


def _safe_int(x):
    if x is None:
        return None
    try:
        return int(x)
    except Exception:
        return None


def _safe_float(x):
    if x is None:
        return None
    try:
        return float(x)
    except Exception:
        return None


def _fmt_num(x, digits=2) -> str:
    if x is None:
        return ""
    try:
        f = float(x)
    except Exception:
        return str(x)
    return f"{f:.{digits}f}".replace(".", ",")


def _date_from_jjmmaa(s: str) -> str | None:
    """Accepte JJMMAA ou JJ/MM/AA ou JJ/MM/AAAA."""
    if not s:
        return None
    s = s.strip().replace(".", "/").replace("-", "/").replace(" ", "")
    if re.fullmatch(r"\d{6}", s):
        jj, mm, aa = s[0:2], s[2:4], s[4:6]
        y2 = int(aa)
        yyyy = 2000 + y2 if y2 <= 69 else 1900 + y2
        try:
            return date(yyyy, int(mm), int(jj)).strftime("%Y-%m-%d")
        except Exception:
            return None
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{2}|\d{4})", s)
    if m:
        jj, mm, yy = m.group(1), m.group(2), m.group(3)
        yyyy = int(yy) if len(yy) == 4 else (2000 + int(yy) if int(yy) <= 69 else 1900 + int(yy))
        try:
            return date(yyyy, int(mm), int(jj)).strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


def _jjmmaa_from_iso(iso_s: str) -> str:
    d = _parse_iso_date(iso_s)
    return d.strftime("%d/%m/%y") if d else ""


def _apply_autocomplete(combo: ttk.Combobox, all_values, typed: str):
    """Filtre les valeurs d'une Combobox en fonction du texte saisi (préfixe)."""
    t = (typed or "").strip().lower()
    if not t:
        combo["values"] = all_values
        return
    filtered = [v for v in all_values if (v or "").lower().startswith(t)]
    combo["values"] = filtered if filtered else all_values


def _format_frequency(period_km, period_months) -> str:
    parts = []
    try:
        if period_km is not None and int(period_km) > 0:
            parts.append(f"{int(period_km)} km")
    except Exception:
        pass
    try:
        if period_months is not None and int(period_months) > 0:
            parts.append(f"{int(period_months)} mois")
    except Exception:
        pass
    return " / ".join(parts) if parts else ""


def _month_diff(d1: date, d2: date) -> int:
    """Nombre de mois entiers entre d1 et d2 (d2 >= d1)."""
    if not d1 or not d2:
        return 0
    m = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    if d2.day < d1.day:
        m -= 1
    return max(0, m)


# ----------------- DB API : Véhicules -----------------

def list_vehicles():
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file
                   FROM vehicules
                   ORDER BY COALESCE(nom,'') COLLATE NOCASE, id""")
    rows = cur.fetchall()
    conn.close()
    return rows


def get_vehicle(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file
                   FROM vehicules WHERE id = ?""", (int(vehicle_id),))
    r = cur.fetchone()
    conn.close()
    return r


def insert_vehicle(nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO vehicules(nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ((nom or "").strip() or None,
                 (marque or "").strip() or None,
                 (modele or "").strip() or None,
                 (motorisation or "").strip() or None,
                 (energie or "").strip() or None,
                 int(annee) if str(annee).strip() != "" else None,
                 (immatriculation or "").strip() or None,
                 (photo_file or "").strip() or None))
    vid = int(cur.lastrowid)
    conn.commit()
    conn.close()
    return vid


def update_vehicle(vehicle_id: int, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_file=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""UPDATE vehicules
                   SET nom=?, marque=?, modele=?, motorisation=?, energie=?, annee=?, immatriculation=?, photo_file=?
                   WHERE id=?""",
                ((nom or "").strip() or None,
                 (marque or "").strip() or None,
                 (modele or "").strip() or None,
                 (motorisation or "").strip() or None,
                 (energie or "").strip() or None,
                 int(annee) if str(annee).strip() != "" else None,
                 (immatriculation or "").strip() or None,
                 (photo_file or "").strip() or None,
                 int(vehicle_id)))
    conn.commit()
    conn.close()


def delete_vehicle(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM vehicules WHERE id=?", (int(vehicle_id),))
    conn.commit()
    conn.close()



# ----------------- DB API : Préconisations constructeur -----------------

def list_preconisations(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT id, texte, created_at
           FROM preconisations
           WHERE vehicule_id = ?
           ORDER BY id DESC""",
        (int(vehicle_id),),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def insert_preconisation(vehicle_id: int, texte: str):
    txt = (texte or "").strip()
    if not txt:
        raise ValueError("Texte vide.")
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO preconisations(vehicule_id, texte, created_at)
           VALUES (?, ?, ?)""",
        (int(vehicle_id), txt, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    conn.commit()
    conn.close()


def update_preconisation(preco_id: int, texte: str):
    txt = (texte or "").strip()
    if not txt:
        raise ValueError("Texte vide.")
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE preconisations SET texte=? WHERE id=?",
        (txt, int(preco_id)),
    )
    conn.commit()
    conn.close()


def delete_preconisation(preco_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM preconisations WHERE id=?", (int(preco_id),))
    conn.commit()
    conn.close()


# ----------------- DB API : Pleins -----------------

def list_pleins(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, date_iso, km, litres, prix_litre, total, lieu
                   FROM pleins WHERE vehicule_id = ?
                   ORDER BY date_iso DESC, km DESC, id DESC""", (int(vehicle_id),))
    rows = cur.fetchall()
    conn.close()
    return rows


def list_pleins_lieux(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT lieu FROM pleins
                   WHERE vehicule_id = ? AND lieu IS NOT NULL AND TRIM(lieu) <> ''
                   ORDER BY lieu COLLATE NOCASE""", (int(vehicle_id),))
    rows = [r["lieu"] for r in cur.fetchall()]
    conn.close()
    return rows


def get_plein(plein_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, vehicule_id, date_iso, km, litres, prix_litre, total, lieu
                   FROM pleins WHERE id=?""", (int(plein_id),))
    r = cur.fetchone()
    conn.close()
    return r


def insert_plein(vehicle_id: int, date_iso: str, km: int, litres: float, prix_litre: float, total=None, lieu=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO pleins(vehicule_id, date_iso, km, litres, prix_litre, total, lieu)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (int(vehicle_id), date_iso, int(km), float(litres), float(prix_litre),
                 _safe_float(total), (lieu or "").strip() or None))
    conn.commit()
    conn.close()


def update_plein(plein_id: int, vehicle_id: int, date_iso: str, km: int, litres: float, prix_litre: float, total=None, lieu=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""UPDATE pleins
                   SET vehicule_id=?, date_iso=?, km=?, litres=?, prix_litre=?, total=?, lieu=?
                   WHERE id=?""",
                (int(vehicle_id), date_iso, int(km), float(litres), float(prix_litre),
                 _safe_float(total), (lieu or "").strip() or None, int(plein_id)))
    conn.commit()
    conn.close()


def delete_plein(plein_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM pleins WHERE id=?", (int(plein_id),))
    conn.commit()
    conn.close()


# ----------------- DB API : Types / Entretiens -----------------

def last_km_any(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("SELECT MAX(km) AS m FROM pleins WHERE vehicule_id=?", (int(vehicle_id),))
    m1 = _safe_int(cur.fetchone()["m"])
    cur.execute("SELECT MAX(km) AS m FROM entretiens WHERE vehicule_id=?", (int(vehicle_id),))
    m2 = _safe_int(cur.fetchone()["m"])
    conn.close()
    if m1 is None:
        return m2
    if m2 is None:
        return m1
    return max(m1, m2)


def list_vehicle_types(vehicle_id: int):
    """Types d'entretien associés au véhicule + flag enabled (rappel affiché)."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT t.id AS type_id,
                          t.nom AS type_name,
                          t.period_km,
                          t.period_months,
                          COALESCE(vtt.enabled, 1) AS enabled
                   FROM vehicule_entretien_types vtt
                   JOIN entretien_types t ON t.id = vtt.type_id
                   WHERE vtt.vehicule_id = ?
                   ORDER BY t.nom COLLATE NOCASE""", (int(vehicle_id),))
    rows = cur.fetchall()
    conn.close()
    return rows


def create_type_for_vehicle(vehicle_id: int, name: str, period_km=None, period_months=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Nom de type vide.")
    pk = _safe_int(period_km) if period_km not in ("", None) else None
    pm = _safe_int(period_months) if period_months not in ("", None) else None

    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""INSERT INTO entretien_types(nom, owner_vehicle_id, period_km, period_months, is_active)
                   VALUES (?, ?, ?, ?, 1)""", (name, int(vehicle_id), pk, pm))
    type_id = int(cur.lastrowid)
    cur.execute("""INSERT INTO vehicule_entretien_types(vehicule_id, type_id, enabled)
                   VALUES (?, ?, 1)""", (int(vehicle_id), type_id))
    conn.commit()
    conn.close()
    return type_id


def update_type(type_id: int, name: str, period_km=None, period_months=None):
    name = (name or "").strip()
    if not name:
        raise ValueError("Nom de type vide.")
    pk = _safe_int(period_km) if period_km not in ("", None) else None
    pm = _safe_int(period_months) if period_months not in ("", None) else None

    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""UPDATE entretien_types SET nom=?, period_km=?, period_months=? WHERE id=?""",
                (name, pk, pm, int(type_id)))
    conn.commit()
    conn.close()


def delete_type_from_vehicle(vehicle_id: int, type_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM vehicule_entretien_types WHERE vehicule_id=? AND type_id=?",
                (int(vehicle_id), int(type_id)))
    cur.execute("SELECT COUNT(*) AS n FROM vehicule_entretien_types WHERE type_id=?", (int(type_id),))
    n_assign = int(cur.fetchone()["n"])
    cur.execute("SELECT COUNT(*) AS n FROM entretiens WHERE type_id=?", (int(type_id),))
    n_ref = int(cur.fetchone()["n"])
    if n_assign == 0 and n_ref == 0:
        cur.execute("DELETE FROM entretien_types WHERE id=?", (int(type_id),))
    conn.commit()
    conn.close()


def set_vehicle_type_enabled(vehicle_id: int, type_id: int, enabled: int):
    """Active/désactive l'affichage du rappel pour un type d'entretien sur un véhicule."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE vehicule_entretien_types SET enabled=? WHERE vehicule_id=? AND type_id=?",
        (1 if enabled else 0, int(vehicle_id), int(type_id)),
    )
    if cur.rowcount == 0:
        cur.execute(
            "INSERT OR REPLACE INTO vehicule_entretien_types(vehicule_id, type_id, enabled) VALUES (?, ?, ?)",
            (int(vehicle_id), int(type_id), 1 if enabled else 0),
        )
    conn.commit()
    conn.close()


def get_last_entretien_for_type(vehicle_id: int, type_id: int):
    """Retourne (date_iso, km) du dernier entretien pour ce type sur ce véhicule."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """SELECT date_iso, km
           FROM entretiens
           WHERE vehicule_id=? AND type_id=?
           ORDER BY date_iso DESC, km DESC, id DESC
           LIMIT 1""",
        (int(vehicle_id), int(type_id)),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return (None, None)
    return (r["date_iso"], r["km"])


def compute_reminder_status(vehicle_id: int, type_id: int, period_km, period_months):
    """Calcule (is_ok, color, label) pour un rappel.

    Règle: si km et/ou mois définis, 'dû' quand AU MOINS un seuil est dépassé.
    Si aucun entretien enregistré -> dû immédiatement.
    """
    current_km = last_km_any(vehicle_id) or 0
    last_date_iso, last_km = get_last_entretien_for_type(vehicle_id, type_id)

    pk = _safe_int(period_km)
    pm = _safe_int(period_months)

    if last_date_iso is None and last_km is None:
        parts = []
        if pk:
            parts.append(f"{pk} km")
        if pm:
            parts.append(f"{pm} mois")
        extra = " / ".join(parts) if parts else ""
        return (False, "red", f"À faire (jamais fait){(' — ' + extra) if extra else ''}")

    # écarts
    km_left = None
    if pk is not None and last_km is not None:
        km_left = pk - (int(current_km) - int(last_km))

    months_left = None
    if pm is not None:
        d_last = _parse_iso_date(last_date_iso)
        if d_last:
            months_left = pm - _month_diff(d_last, date.today())

    overdue = False
    if km_left is not None and km_left <= 0:
        overdue = True
    if months_left is not None and months_left <= 0:
        overdue = True

    if overdue:
        parts = []
        if km_left is not None and km_left <= 0:
            parts.append(f"{abs(km_left)} km")
        if months_left is not None and months_left <= 0:
            parts.append(f"{abs(months_left)} mois")
        suffix = " / ".join(parts) if parts else ""
        return (False, "red", f"À faire depuis {suffix}".strip())
    else:
        parts = []
        if km_left is not None:
            parts.append(f"{km_left} km")
        if months_left is not None:
            parts.append(f"{months_left} mois")
        suffix = " / ".join(parts) if parts else ""
        if not suffix:
            return (True, "green", "OK")

        # Pré-alerte : si la fréquence est > 6 mois et que c'est dû dans <= 6 mois → orange
        try:
            pm_int = int(pm) if pm is not None else None
        except Exception:
            pm_int = None
        if pm_int is not None and pm_int > 6 and months_left is not None and 0 < months_left <= 6:
            return (True, "orange", f"À faire dans {suffix}".strip())

        return (True, "green", f"À faire dans {suffix}".strip())


def list_entretiens_full(vehicle_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT e.id, e.date_iso, e.km,
                          COALESCE(t.nom, e.intervention) AS type_name,
                          e.kind, e.cout, e.performed_by, e.battery_voltage, e.details, e.type_id
                   FROM entretiens e
                   LEFT JOIN entretien_types t ON t.id = e.type_id
                   WHERE e.vehicule_id = ?
                   ORDER BY e.date_iso DESC, e.km DESC, e.id DESC""", (int(vehicle_id),))
    rows = cur.fetchall()
    conn.close()
    return rows


def get_entretien(entretien_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("""SELECT id, vehicule_id, type_id, intervention, date_iso, km, cout, details, kind, performed_by, battery_voltage
                   FROM entretiens WHERE id=?""", (int(entretien_id),))
    r = cur.fetchone()
    conn.close()
    return r


def insert_entretien(vehicle_id: int, date_iso: str, km: int, kind: str, type_id: int,
                    cout=None, performed_by=None, details=None, battery_voltage=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("SELECT nom FROM entretien_types WHERE id=?", (int(type_id),))
    rr = cur.fetchone()
    snapshot = rr["nom"] if rr else None
    cur.execute("""INSERT INTO entretiens(vehicule_id, type_id, intervention, date_iso, km, cout, details, kind, performed_by, battery_voltage)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(vehicle_id), int(type_id), snapshot, date_iso, int(km), _safe_float(cout),
                 (details or "").strip() or None, (kind or "").strip() or None,
                 (performed_by or "").strip() or None, _safe_float(battery_voltage)))
    conn.commit()
    conn.close()


def update_entretien(entretien_id: int, vehicle_id: int, date_iso: str, km: int, kind: str, type_id: int,
                    cout=None, performed_by=None, details=None, battery_voltage=None):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("SELECT nom FROM entretien_types WHERE id=?", (int(type_id),))
    rr = cur.fetchone()
    snapshot = rr["nom"] if rr else None
    cur.execute("""UPDATE entretiens
                   SET vehicule_id=?, type_id=?, intervention=?, date_iso=?, km=?, cout=?, details=?, kind=?, performed_by=?, battery_voltage=?
                   WHERE id=?""",
                (int(vehicle_id), int(type_id), snapshot, date_iso, int(km), _safe_float(cout),
                 (details or "").strip() or None, (kind or "").strip() or None,
                 (performed_by or "").strip() or None, _safe_float(battery_voltage),
                 int(entretien_id)))
    conn.commit()
    conn.close()


def delete_entretien(entretien_id: int):
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM entretiens WHERE id=?", (int(entretien_id),))
    conn.commit()
    conn.close()


def conso_moy_l100(vehicle_id: int):
    """Conso moyenne (L/100) basée sur pleins: SUM(litres)/(max_km-min_km)*100. Nécessite >=2 pleins."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT MIN(km) AS kmin, MAX(km) AS kmax, SUM(litres) AS lsum, COUNT(*) AS n FROM pleins WHERE vehicule_id=?",
        (int(vehicle_id),),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    try:
        n = int(r["n"] or 0)
    except Exception:
        n = 0
    if n < 2:
        return None
    kmin = _safe_int(r["kmin"])
    kmax = _safe_int(r["kmax"])
    lsum = _safe_float(r["lsum"])
    if kmin is None or kmax is None or lsum is None:
        return None
    dist = kmax - kmin
    if dist <= 0:
        return None
    return (lsum / dist) * 100.0


def get_last_battery_voltage(vehicle_id: int):
    """Retourne le dernier voltage batterie (float) renseigné dans les entretiens, ou None."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT battery_voltage
        FROM entretiens
        WHERE vehicule_id = ? AND battery_voltage IS NOT NULL
        ORDER BY date_iso DESC, km DESC, id DESC
        LIMIT 1
        """,
        (int(vehicle_id),),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    try:
        return float(r["battery_voltage"])
    except Exception:
        return None


def _recent_cost_for_type(vehicle_id: int, type_id: int):
    """Coût le plus récent (non NULL) pour un type d'entretien sur un véhicule."""
    conn = _connect_db()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT cout
        FROM entretiens
        WHERE vehicule_id = ? AND type_id = ? AND cout IS NOT NULL
        ORDER BY date_iso DESC, km DESC, id DESC
        LIMIT 1
        """,
        (int(vehicle_id), int(type_id)),
    )
    r = cur.fetchone()
    conn.close()
    if not r:
        return None
    try:
        return float(r["cout"])
    except Exception:
        return None


def estimate_maintenance_cost_next_months(vehicle_id: int, horizon_months: int = 6):
    """Estimation des coûts à prévoir sur les prochains mois.

    Pour chaque type cochée (enabled=1) :
    - Si period_months > 0 :
        on regarde la dernière date d'entretien de ce type.
        On calcule dans combien de mois il est dû.
        On compte les occurrences qui tombent dans la fenêtre [0, horizon_months].
    - On utilise le coût le plus récent connu pour ce type.
    """
    total = 0.0
    any_included = False

    for t in list_vehicle_types(vehicle_id):
        enabled = 1
        try:
            enabled = int(t["enabled"]) if t["enabled"] is not None else 1
        except Exception:
            enabled = 1
        if enabled != 1:
            continue

        pm = t["period_months"]
        try:
            pm = int(pm) if pm is not None else 0
        except Exception:
            pm = 0
        if pm <= 0:
            continue

        last_date_iso, _last_km = get_last_entretien_for_type(vehicle_id, int(t["type_id"]))
        if not last_date_iso:
            due_in_months = 0
        else:
            last_d = _parse_iso_date(last_date_iso)
            if not last_d:
                due_in_months = 0
            else:
                months_since = _month_diff(last_d, date.today())
                due_in_months = pm - months_since

        if due_in_months > horizon_months:
            expected = 0
        else:
            first = max(0, due_in_months)
            expected = 1 + max(0, (horizon_months - first) // pm)

        if expected <= 0:
            continue

        cost = _recent_cost_for_type(vehicle_id, int(t["type_id"]))
        if cost is None or cost <= 0:
            continue

        total += cost * expected
        any_included = True

    return total if any_included else None


# ----------------- Modales -----------------

class PleinEditor(tk.Toplevel):
    def __init__(self, parent, vehicle_id: int, plein_id: int, on_saved):
        super().__init__(parent)
        self.title("Modifier plein")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.vehicle_id = int(vehicle_id)
        self.plein_id = int(plein_id)
        self.on_saved = on_saved

        r = get_plein(self.plein_id)
        if not r:
            messagebox.showerror("Erreur", "Plein introuvable.")
            self.destroy()
            return

        self.var_date = tk.StringVar(value=_jjmmaa_from_iso(r["date_iso"] or ""))
        self.var_km = tk.StringVar(value=str(r["km"] if r["km"] is not None else ""))
        self.var_litres = tk.StringVar(value="" if r["litres"] is None else str(r["litres"]).replace(".", ","))
        self.var_prix = tk.StringVar(value="" if r["prix_litre"] is None else str(r["prix_litre"]).replace(".", ","))
        self.var_total = tk.StringVar(value="" if r["total"] is None else str(r["total"]).replace(".", ","))
        self.var_lieu = tk.StringVar(value=r["lieu"] or "")

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Date (JJMMAA) :").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.var_date, width=12).grid(row=0, column=1, sticky="w", padx=(6, 16))
        ttk.Label(frm, text="Km :").grid(row=0, column=2, sticky="w")
        ttk.Entry(frm, textvariable=self.var_km, width=10).grid(row=0, column=3, sticky="w")

        ttk.Label(frm, text="Litres :").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_litres, width=12).grid(row=1, column=1, sticky="w", padx=(6, 16), pady=(10, 0))
        ttk.Label(frm, text="Prix/L :").grid(row=1, column=2, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_prix, width=10).grid(row=1, column=3, sticky="w", pady=(10, 0))

        ttk.Label(frm, text="Total :").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_total, width=12).grid(row=2, column=1, sticky="w", padx=(6, 16), pady=(10, 0))
        ttk.Label(frm, text="Lieu :").grid(row=2, column=2, sticky="w", pady=(10, 0))

        self._all_lieux = list_pleins_lieux(self.vehicle_id)
        self.lieu_cb = ttk.Combobox(frm, textvariable=self.var_lieu, values=self._all_lieux, state="normal", width=24)
        self.lieu_cb.grid(row=2, column=3, sticky="w", padx=(6, 0), pady=(10, 0))
        self.lieu_cb.bind("<KeyRelease>", lambda e: _apply_autocomplete(self.lieu_cb, self._all_lieux, self.var_lieu.get()))

        ttk.Label(frm, text="Si Total est vide → calcul auto (Litres × Prix/L).").grid(row=3, column=0, columnspan=4, sticky="w", pady=(10, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=4, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="Annuler", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Enregistrer", command=self._save).grid(row=0, column=1)

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _save(self):
        date_iso = _date_from_jjmmaa(self.var_date.get().strip())
        if not date_iso:
            messagebox.showwarning("Date", "Date invalide (JJMMAA ou JJ/MM/AA).")
            return

        km = _safe_int(self.var_km.get().strip().lower().replace("km", "").strip())
        if km is None or km < 0:
            messagebox.showwarning("Km", "Kilométrage invalide.")
            return

        litres = _safe_float(self.var_litres.get().strip().replace(",", "."))
        if litres is None or litres <= 0:
            messagebox.showwarning("Litres", "Litres invalide.")
            return

        prix = _safe_float(self.var_prix.get().strip().replace(",", "."))
        if prix is None or prix <= 0:
            messagebox.showwarning("Prix/L", "Prix/L invalide.")
            return

        total_in = self.var_total.get().strip().replace(",", ".")
        if total_in:
            total = _safe_float(total_in)
            if total is None or total <= 0:
                messagebox.showwarning("Total", "Total invalide (ou laisse vide).")
                return
        else:
            total = litres * prix

        lieu = self.var_lieu.get().strip()
        update_plein(self.plein_id, self.vehicle_id, date_iso, km, litres, prix, total, lieu)

        if callable(self.on_saved):
            self.on_saved()
        self.destroy()


class EntretienEditor(tk.Toplevel):
    def __init__(self, parent, vehicle_id: int, entretien_id: int, type_choices, type_name_to_id, on_saved):
        super().__init__(parent)
        self.title("Modifier entretien")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.vehicle_id = int(vehicle_id)
        self.entretien_id = int(entretien_id)
        self.type_choices = list(type_choices)
        self.type_name_to_id = dict(type_name_to_id)
        self.on_saved = on_saved

        r = get_entretien(self.entretien_id)
        if not r:
            messagebox.showerror("Erreur", "Entretien introuvable.")
            self.destroy()
            return

        self.var_date = tk.StringVar(value=_jjmmaa_from_iso(r["date_iso"] or ""))
        self.var_km = tk.StringVar(value=str(r["km"] if r["km"] is not None else ""))
        self.var_kind = tk.StringVar(value=r["kind"] or "Entretien")

        sel_name = ""
        if r["type_id"]:
            for name, tid in self.type_name_to_id.items():
                if tid == r["type_id"]:
                    sel_name = name
                    break
        if not sel_name:
            sel_name = r["intervention"] or (self.type_choices[0] if self.type_choices else "")
        self.var_type = tk.StringVar(value=sel_name)

        self.var_cost = tk.StringVar(value="" if r["cout"] is None else str(r["cout"]).replace(".", ","))
        self.var_by = tk.StringVar(value=r["performed_by"] or "")
        self.var_vbat = tk.StringVar(value="" if r["battery_voltage"] is None else f"{float(r['battery_voltage']):.2f}".replace(".", ","))
        self.var_details = tk.StringVar(value=r["details"] or "")

        frm = ttk.Frame(self, padding=12)
        frm.grid(row=0, column=0, sticky="nsew")

        ttk.Label(frm, text="Date (JJMMAA) :").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.var_date, width=12).grid(row=0, column=1, sticky="w", padx=(6, 16))
        ttk.Label(frm, text="Km :").grid(row=0, column=2, sticky="w")
        ttk.Entry(frm, textvariable=self.var_km, width=10).grid(row=0, column=3, sticky="w")

        ttk.Label(frm, text="Intervention :").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(frm, textvariable=self.var_kind, state="readonly",
                    values=["Réparation", "Entretien", "Entretien & Réparation"]).grid(row=1, column=1, sticky="w", padx=(6, 16), pady=(10, 0))
        ttk.Label(frm, text="Type d'entretien :").grid(row=1, column=2, sticky="w", pady=(10, 0))
        ttk.Combobox(frm, textvariable=self.var_type, state="readonly", values=self.type_choices).grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(10, 0))

        ttk.Label(frm, text="Coût :").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_cost, width=12).grid(row=2, column=1, sticky="w", padx=(6, 16), pady=(10, 0))
        ttk.Label(frm, text="Effectué par :").grid(row=2, column=2, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_by, width=26).grid(row=2, column=3, sticky="w", padx=(6, 0), pady=(10, 0))

        ttk.Label(frm, text="Tension Batterie (V) :").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_vbat, width=12).grid(row=3, column=1, sticky="w", padx=(6, 16), pady=(10, 0))
        ttk.Label(frm, text="Détail :").grid(row=3, column=2, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_details, width=26).grid(row=3, column=3, sticky="w", padx=(6, 0), pady=(10, 0))

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=4, sticky="e", pady=(14, 0))
        ttk.Button(btns, text="Annuler", command=self.destroy).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Enregistrer", command=self._save).grid(row=0, column=1)

        self.bind("<Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _save(self):
        date_iso = _date_from_jjmmaa(self.var_date.get().strip())
        if not date_iso:
            messagebox.showwarning("Date", "Date invalide.")
            return

        km = _safe_int(self.var_km.get().strip().lower().replace("km", "").strip())
        if km is None or km < 0:
            messagebox.showwarning("Km", "Kilométrage invalide.")
            return

        kind = self.var_kind.get().strip()
        if kind not in ("Réparation", "Entretien", "Entretien & Réparation"):
            kind = "Entretien"

        type_name = self.var_type.get().strip()
        type_id = self.type_name_to_id.get(type_name)
        if not type_id:
            messagebox.showwarning("Type", "Choisis un type d'entretien.")
            return

        cost_in = self.var_cost.get().strip().replace(",", ".")
        cout = None
        if cost_in:
            try:
                cout = float(cost_in)
            except Exception:
                messagebox.showwarning("Coût", "Coût invalide.")
                return

        by = self.var_by.get().strip()

        vbat_in = self.var_vbat.get().strip().replace(",", ".")
        vbat = None
        if vbat_in:
            try:
                vbat = float(vbat_in)
            except Exception:
                messagebox.showwarning("Vbat", "Valeur invalide.")
                return
            if not (5.00 <= vbat <= 25.99):
                messagebox.showwarning("Vbat", "Vbat doit être entre 5.00 et 25.99.")
                return

        details = self.var_details.get().strip()

        update_entretien(self.entretien_id, self.vehicle_id, date_iso, km, kind, type_id, cout, by, details, vbat)
        if callable(self.on_saved):
            self.on_saved()
        self.destroy()


# ----------------- Application -----------------

class GarageApp(tk.Tk):
    def __init__(self):
        super().__init__()

        # Fonts
        _base = tkfont.nametofont("TkDefaultFont")
        _fam = _base.actual("family")
        _sz = int(_base.actual("size"))
        self.font_card_title = tkfont.Font(family=_fam, size=_sz + 7, weight="bold")
        self.font_rem_title = tkfont.Font(family=_fam, size=_sz + 4, weight="bold")
        self.font_rem_item = tkfont.Font(family=_fam, size=_sz + 4)
        self.font_detail_label = tkfont.Font(family=_fam, size=_sz, weight="bold")
        self.font_info2_bold = tkfont.Font(family=_fam, size=_sz + 2, weight="bold")

        self.title(APP_TITLE)
        self.geometry("1400x950")
        self.minsize(1180, 720)

        if not os.path.exists(DB_FILE):
            messagebox.showerror("DB introuvable", f"Impossible de trouver :\n{DB_FILE}\n\nMets garage.db à côté du script.")
            raise SystemExit(1)

        _ensure_schema()
        _ensure_assets_dir()

        self.vehicles_rows = list_vehicles()
        if not self.vehicles_rows:
        messagebox.showinfo("Aucun véhicule", "La base est vide. Ajoutez un premier véhicule")
        self.vehicles_rows = []   # au cas où
        return

        self.active_vehicle_id = int(self.vehicles_rows[0]["id"])
        self._general_card_imgs = {}
        self._veh_photo_img = None
        self._veh_mode = "view"  # view/add/edit
        self._veh_photo_src_path = None
        self._pleins_lieux_all = []
        self._type_name_to_id = {}
        self.selected_type_id = None

        self.status = tk.StringVar(value=f"DB: {os.path.basename(DB_FILE)}")

        self._build_ui()
        self._refresh_all()

    # ---------- UI Shell ----------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.nb = ttk.Notebook(self)
        self.nb.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        self.tab_general = ttk.Frame(self.nb, padding=10)
        self.tab_vehicules = ttk.Frame(self.nb, padding=10)
        self.tab_pleins = ttk.Frame(self.nb, padding=10)
        self.tab_ent = ttk.Frame(self.nb, padding=10)

        self.nb.add(self.tab_general, text="Général")
        self.nb.add(self.tab_vehicules, text="Véhicules")
        self.nb.add(self.tab_pleins, text="Pleins")
        self.nb.add(self.tab_ent, text="Entretiens")

        self._build_general_tab()
        self._build_vehicules_tab()
        self._build_pleins_tab()
        self._build_entretiens_tab()

        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=(10, 4)).grid(
            row=1, column=0, sticky="ew", padx=10, pady=(0, 10)
        )

    def _set_status(self, txt: str):
        self.status.set(txt)

    # ---------- Général ----------
    def _build_general_tab(self):
        self.tab_general.columnconfigure(0, weight=1)
        self.tab_general.rowconfigure(1, weight=1)

        head = ttk.Frame(self.tab_general)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(1, weight=1)

        nav = ttk.Frame(head)
        nav.grid(row=0, column=1, sticky="e")
        self.btn_prev = ttk.Button(nav, text="◀", width=3, command=self._general_prev_page)
        self.btn_next = ttk.Button(nav, text="▶", width=3, command=self._general_next_page)
        self.lbl_page = ttk.Label(nav, text="")
        self.btn_prev.grid(row=0, column=0, padx=(0, 6))
        self.lbl_page.grid(row=0, column=1, padx=(0, 6))
        self.btn_next.grid(row=0, column=2)

        self.general_cards = ttk.Frame(self.tab_general)
        self.general_cards.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        self.general_cards.columnconfigure(0, weight=1)
        self.general_cards.columnconfigure(1, weight=1)
        self.general_cards.rowconfigure(0, weight=1)

        self.general_page = 0

    def _general_prev_page(self):
        if self.general_page > 0:
            self.general_page -= 1
            self._refresh_general_overview()

    def _general_next_page(self):
        total = len(self.vehicles_rows)
        max_page = max(0, (total - 1) // 2)
        if self.general_page < max_page:
            self.general_page += 1
            self._refresh_general_overview()

    def _select_vehicle_from_general(self, vehicle_id: int):
        self.active_vehicle_id = int(vehicle_id)
        self._refresh_all_tabs_after_vehicle_change(source="general_click")

    def _refresh_general_overview(self):
        for w in self.general_cards.winfo_children():
            w.destroy()
        self._general_card_imgs = {}

        total = len(self.vehicles_rows)
        max_page = max(0, (total - 1) // 2)
        if self.general_page > max_page:
            self.general_page = max_page

        if total <= 2:
            self.btn_prev.grid_remove()
            self.btn_next.grid_remove()
            self.lbl_page.grid_remove()
        else:
            self.btn_prev.grid()
            self.btn_next.grid()
            self.lbl_page.grid()
            self.btn_prev.state(["!disabled"] if self.general_page > 0 else ["disabled"])
            self.btn_next.state(["!disabled"] if self.general_page < max_page else ["disabled"])
            self.lbl_page.config(text=f"{self.general_page + 1}/{max_page + 1}")

        start = self.general_page * 2
        show_rows = self.vehicles_rows[start:start + 2]
        if len(show_rows) == 1:
            self._build_general_card(show_rows[0], row=0, col=0, colspan=2)
        else:
            for col, r in enumerate(show_rows):
                self._build_general_card(r, row=0, col=col, colspan=1)

    def _build_general_card(self, r, row: int, col: int, colspan: int):
        vid = int(r["id"])
        title = r["nom"] or f"Véhicule #{vid}"

        card = ttk.Frame(self.general_cards, padding=14)
        card.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=10, pady=10)
        self.general_cards.columnconfigure(col, weight=1)
        self.general_cards.rowconfigure(row, weight=1)
        card.columnconfigure(1, weight=1)

        card.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        title_lbl = ttk.Label(card, text=title, font=self.font_card_title, anchor="center")
        title_lbl.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        title_lbl.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        cons = conso_moy_l100(vid)
        cons_txt = (f"{_fmt_num(cons, 2)} L/100 km" if cons is not None else "—")
        conso_lbl = ttk.Label(card, text=f"Conso moy. : {cons_txt}", font=self.font_info2_bold, foreground="#66B3FF")
        conso_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 8))
        conso_lbl.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        vbat = get_last_battery_voltage(vid)
        if vbat is None:
            bat_msg, bat_color = "—", ""
        else:
            if vbat <= 12.0:
                bat_msg = "Tension en dessous de 12V : Attention décharge critique, prévoir remplacement"
                bat_color = "red"
            elif 12.1 <= vbat <= 12.3:
                bat_msg = "Tension de batterie faible : À recharger"
                bat_color = "red"
            elif 12.4 <= vbat <= 12.5:
                bat_msg = "Batterie limite mais ça passe"
                bat_color = "orange"
            else:
                bat_msg = "Batterie en bonne santé"
                bat_color = "green"
            bat_msg = f"{bat_msg} ({vbat:.2f} V)"
        bat_line = ttk.Label(card, text=f"État de la Batterie : {bat_msg}", font=self.font_info2_bold,
                             foreground=bat_color, wraplength=1100, justify="left")
        bat_line.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 12))
        bat_line.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        img = _load_vehicle_photo_tk(r["photo_file"], max_w=270, max_h=165)
        self._general_card_imgs[vid] = img
        photo = ttk.Label(card, text="(aucune photo)")
        photo.grid(row=3, column=0, sticky="nw")
        if img:
            photo.config(image=img, text="")
        photo.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        est = estimate_maintenance_cost_next_months(vid, horizon_months=6)
        est_txt = (f"{_fmt_num(est, 0)} €" if est is not None else "—")
        cost_lbl = ttk.Label(card, text=f"Coût à prévoir pour les 6 prochains mois ≃ {est_txt}", font=self.font_rem_item, foreground="#66B3FF")
        cost_lbl.grid(row=4, column=0, sticky="w", pady=(10, 0))
        cost_lbl.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        details = ttk.Frame(card)
        details.grid(row=3, column=1, rowspan=2, sticky="nw", padx=(14, 0))
        details.columnconfigure(1, weight=1)

        def row_get(key, default=""):
            try:
                if key in r.keys():
                    v = r[key]
                    return default if v is None else v
            except Exception:
                pass
            return default

        def add_row(label, value, rr):
            ttk.Label(details, text=label + " :", font=self.font_detail_label).grid(row=rr, column=0, sticky="e", padx=(0, 10), pady=3)
            ttk.Label(details, text=value, wraplength=800).grid(row=rr, column=1, sticky="w", pady=3)

        add_row("Marque", row_get("marque", ""), 0)
        add_row("Modèle", row_get("modele", ""), 1)
        add_row("Motorisation", row_get("motorisation", ""), 2)
        add_row("Énergie", row_get("energie", ""), 3)
        add_row("Année", "" if row_get("annee", None) is None else str(row_get("annee")), 4)
        add_row("Immat.", row_get("immatriculation", ""), 5)
        add_row("Dernier km", str(last_km_any(vid) or ""), 6)

        reminders = ttk.Frame(card)
        reminders.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        reminders.columnconfigure(0, weight=1)
        ttk.Label(reminders, text="Rappels (types cochés uniquement)", font=self.font_rem_title).grid(row=0, column=0, sticky="w", pady=(0, 6))

        types = list_vehicle_types(vid)
        line_row = 1
        shown = 0
        for t in types:
            # IMPORTANT : on filtre strictement sur enabled == 1
            try:
                enabled = int(t["enabled"]) if t["enabled"] is not None else 1
            except Exception:
                enabled = 1
            if enabled != 1:
                continue

            type_id = int(t["type_id"])
            type_name = t["type_name"] or ""
            is_ok, color, when_txt = compute_reminder_status(vid, type_id, t["period_km"], t["period_months"])
            sym = "V" if is_ok else "X"
            suffix = f" — {when_txt}" if when_txt else ""

            ttk.Label(
                reminders,
                text=f"{sym}  {type_name}{suffix}",
                font=self.font_rem_item,
                foreground=color,
                wraplength=1100,
                justify="left",
            ).grid(row=line_row, column=0, sticky="w", pady=2)
            line_row += 1
            shown += 1

        if shown == 0:
            ttk.Label(reminders, text="(Rappels désactivés pour ce véhicule)", font=self.font_rem_item).grid(row=1, column=0, sticky="w")

    # ---------- Véhicules ----------
    def _build_vehicules_tab(self):
        self.tab_vehicules.columnconfigure(0, weight=1)

        top = ttk.Frame(self.tab_vehicules)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Véhicule :").grid(row=0, column=0, sticky="w")
        self.veh_vehicle_var = tk.StringVar(value="")
        self.veh_vehicle_cb = ttk.Combobox(top, textvariable=self.veh_vehicle_var, state="readonly")
        self.veh_vehicle_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.veh_vehicle_cb.bind("<<ComboboxSelected>>", self._on_veh_vehicle_change)

        btns = ttk.Frame(self.tab_vehicules)
        btns.grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(btns, text="Ajouter", command=self._veh_add_mode).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Modifier", command=self._veh_edit_mode).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btns, text="Supprimer", command=self._veh_delete).grid(row=0, column=2)
        self.veh_btn_save_top = ttk.Button(btns, text="Enregistrer", command=self._veh_save)
        self.veh_btn_save_top.grid(row=0, column=3, padx=(8, 0))

        body = ttk.Frame(self.tab_vehicules)
        body.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        body.columnconfigure(1, weight=1)

        photo_box = ttk.Labelframe(body, text="Photo", padding=10)
        photo_box.grid(row=0, column=0, sticky="nw")
        self.veh_photo_label = ttk.Label(photo_box, text="(aucune photo)")
        self.veh_photo_label.grid(row=0, column=0, sticky="nw")
        self.veh_photo_hint = ttk.Label(photo_box, text="")
        self.veh_photo_hint.grid(row=2, column=0, sticky="w", pady=(6, 0))

        pick = ttk.Frame(photo_box)
        pick.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        ttk.Label(pick, text="Sélectionner une photo :").grid(row=0, column=0, sticky="w")
        ttk.Button(pick, text="Parcourir", command=self._veh_pick_photo).grid(row=0, column=1, sticky="w", padx=(10, 0))

        form = ttk.Labelframe(body, text="Détails tech", padding=10)
        form.grid(row=0, column=1, sticky="nw")

        # ---- Préconisations constructeur (notes libres) ----
        body.rowconfigure(1, weight=1)

        preco_box = ttk.Labelframe(body, text="Préconisations constructeur", padding=10)
        preco_box.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        preco_box.columnconfigure(0, weight=1)
        preco_box.rowconfigure(1, weight=1)

        add_line = ttk.Frame(preco_box)
        add_line.grid(row=0, column=0, sticky="ew")
        add_line.columnconfigure(1, weight=1)

        ttk.Button(add_line, text="+", width=3, command=self._preco_add).grid(row=0, column=0, sticky="w")
        self.preco_entry_var = tk.StringVar(value="")
        ttk.Entry(add_line, textvariable=self.preco_entry_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        # Liste sélectionnable (chaque ligne = une préco)
        self.preco_list = tk.Listbox(preco_box, height=6)
        self.preco_list.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        self.preco_list.bind("<<ListboxSelect>>", self._on_preco_select)

        actions_p = ttk.Frame(preco_box)
        actions_p.grid(row=2, column=0, sticky="e", pady=(10, 0))
        ttk.Button(actions_p, text="Enregistrer", command=self._preco_save).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions_p, text="Modifier", command=self._preco_update).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(actions_p, text="Supprimer", command=self._preco_delete).grid(row=0, column=2)

        self.preco_selected_id = None
        self._preco_rows = []

        self.veh_vars = {
            "nom": tk.StringVar(value=""),
            "marque": tk.StringVar(value=""),
            "modele": tk.StringVar(value=""),
            "motorisation": tk.StringVar(value=""),
            "energie": tk.StringVar(value=""),
            "annee": tk.StringVar(value=""),
            "immatriculation": tk.StringVar(value=""),
            "dernier_km": tk.StringVar(value=""),
        }
        self.veh_entries = {}

        fields = [
            ("Nom", "nom"),
            ("Marque", "marque"),
            ("Modele", "modele"),
            ("Motorisation", "motorisation"),
            ("Énergie", "energie"),
            ("Année", "annee"),
            ("Immat", "immatriculation"),
            ("Dernier Km", "dernier_km"),
        ]
        for i, (lab, key) in enumerate(fields):
            ttk.Label(form, text=lab + " :").grid(row=i, column=0, sticky="e", padx=(0, 10), pady=4)
            e = ttk.Entry(form, textvariable=self.veh_vars[key], width=38)
            e.grid(row=i, column=1, sticky="w", pady=4)
            self.veh_entries[key] = e

        self._veh_set_mode("view")

    def _on_veh_vehicle_change(self, _evt=None):
        idx = self.veh_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._veh_set_mode("view")
        self._refresh_all_tabs_after_vehicle_change(source="vehicules")

    def _veh_set_mode(self, mode: str):
        self._veh_mode = mode
        editable = mode in ("add", "edit")
        state = "normal" if editable else "readonly"

        for k, ent in self.veh_entries.items():
            if k == "dernier_km":
                ent.config(state="readonly")
            else:
                ent.config(state=state)
        if hasattr(self, "veh_btn_save_top"):
            self.veh_btn_save_top.state(["!disabled"] if editable else ["disabled"])
        if hasattr(self, "veh_btn_cancel_top"):
            self.veh_btn_cancel_top.state(["!disabled"] if editable else ["disabled"])
        self.veh_photo_hint.config(text=("PNG uniquement. La photo sera copiée dans ./assets" if editable else ""))

        if not editable:
            self._veh_photo_src_path = None

    def _veh_add_mode(self):
        self._veh_photo_src_path = None
        for k in self.veh_vars:
            self.veh_vars[k].set("")
        self._veh_photo_img = None
        self.veh_photo_label.config(image="", text="(aucune photo)")
        self._veh_set_mode("add")
        self._set_status("Mode ajout véhicule")

    def _veh_edit_mode(self):
        self._veh_set_mode("edit")
        self._set_status("Mode modification véhicule")

    def _veh_cancel(self):
        self._veh_set_mode("view")
        self._refresh_vehicle_forms()

        self._refresh_preconisations()
        self._set_status("Annulé")

    def _veh_pick_photo(self):
        if self._veh_mode not in ("add", "edit"):
            messagebox.showinfo("Photo", "Clique sur Ajouter ou Modifier pour changer la photo.")
            return
        path = filedialog.askopenfilename(
            title="Choisir une photo PNG",
            filetypes=[("PNG", "*.png"), ("Tous les fichiers", "*.*")]
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            messagebox.showwarning("Photo", "Format non supporté. Choisis un PNG (.png).")
            return

        self._veh_photo_src_path = path
        try:
            img = tk.PhotoImage(file=path)
            w, h = img.width(), img.height()
            s = max(1, int(max(w / 288, h / 176)))
            if s > 1:
                img = img.subsample(s, s)
            self._veh_photo_img = img
            self.veh_photo_label.config(image=img, text="")
        except Exception:
            self._veh_photo_img = None
            self.veh_photo_label.config(image="", text="(aperçu impossible)")

    def _veh_save(self):
        if self._veh_mode not in ("add", "edit"):
            return

        nom = self.veh_vars["nom"].get()
        marque = self.veh_vars["marque"].get()
        modele = self.veh_vars["modele"].get()
        motorisation = self.veh_vars["motorisation"].get()
        energie = self.veh_vars["energie"].get()
        annee = self.veh_vars["annee"].get()
        immat = self.veh_vars["immatriculation"].get()

        existing = get_vehicle(self.active_vehicle_id)
        photo_file = existing["photo_file"] if existing else None

        if self._veh_photo_src_path:
            try:
                photo_file = _copy_vehicle_photo(
                    self._veh_photo_src_path,
                    self.active_vehicle_id if self._veh_mode == "edit" else None
                )
            except Exception as e:
                messagebox.showerror("Photo", str(e))
                return

        if self._veh_mode == "add":
            vid = insert_vehicle(nom, marque, modele, motorisation, energie, annee, immat, photo_file=photo_file)
            self.active_vehicle_id = vid
            self._set_status("Véhicule ajouté.")
        else:
            update_vehicle(self.active_vehicle_id, nom, marque, modele, motorisation, energie, annee, immat, photo_file=photo_file)
            self._set_status("Véhicule modifié.")

        self._veh_set_mode("view")
        self.vehicles_rows = list_vehicles()
        self._refresh_all()

    def _veh_delete(self):
        if not self.active_vehicle_id:
            return
        if not messagebox.askyesno(
            "Confirmer",
            "Supprimer ce véhicule ?\n\nAttention : si des pleins/entretiens existent, la suppression peut échouer."
        ):
            return
        try:
            delete_vehicle(self.active_vehicle_id)
        except Exception as e:
            messagebox.showerror("Suppression impossible", str(e))
            return

        self.vehicles_rows = list_vehicles()
        if not self.vehicles_rows:
            messagebox.showinfo("Info", "Plus aucun véhicule dans la flotte.")
            self.destroy()
            return
        self.active_vehicle_id = int(self.vehicles_rows[0]["id"])
        self._refresh_all()
        self._set_status("Véhicule supprimé.")

    # ---------- Préconisations constructeur ----------
    def _refresh_preconisations(self):
        if not hasattr(self, "preco_list"):
            return
        try:
            self._preco_rows = list_preconisations(self.active_vehicle_id)
        except Exception:
            self._preco_rows = []
        self.preco_list.delete(0, "end")
        for r in self._preco_rows:
            txt = r["texte"] if "texte" in r.keys() else r[1]
            self.preco_list.insert("end", txt)
        self.preco_selected_id = None
        if hasattr(self, "preco_entry_var"):
            self.preco_entry_var.set("")

    def _on_preco_select(self, _evt=None):
        if not self._preco_rows:
            return
        sel = self.preco_list.curselection()
        if not sel:
            return
        idx = int(sel[0])
        if idx < 0 or idx >= len(self._preco_rows):
            return
        r = self._preco_rows[idx]
        self.preco_selected_id = int(r["id"] if "id" in r.keys() else r[0])
        txt = r["texte"] if "texte" in r.keys() else r[1]
        self.preco_entry_var.set(txt)

    def _preco_add(self):
        """Bouton + : ajoute directement la ligne saisie."""
        self._preco_save()

    def _preco_save(self):
        txt = (self.preco_entry_var.get() if hasattr(self, "preco_entry_var") else "").strip()
        if not txt:
            messagebox.showinfo("Préconisations", "Entre un texte avant d'enregistrer.")
            return
        try:
            insert_preconisation(self.active_vehicle_id, txt)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._refresh_preconisations()
        self._set_status("Préconisation enregistrée.")

    def _preco_update(self):
        if not getattr(self, "preco_selected_id", None):
            messagebox.showinfo("Sélection", "Sélectionne une préconisation dans la liste.")
            return
        txt = (self.preco_entry_var.get() if hasattr(self, "preco_entry_var") else "").strip()
        if not txt:
            messagebox.showinfo("Préconisations", "Texte vide.")
            return
        try:
            update_preconisation(self.preco_selected_id, txt)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._refresh_preconisations()
        self._set_status("Préconisation modifiée.")

    def _preco_delete(self):
        if not getattr(self, "preco_selected_id", None):
            messagebox.showinfo("Sélection", "Sélectionne une préconisation dans la liste.")
            return
        if not messagebox.askyesno("Confirmer", "Supprimer cette préconisation ?"):
            return
        try:
            delete_preconisation(self.preco_selected_id)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._refresh_preconisations()
        self._set_status("Préconisation supprimée.")



    def _refresh_vehicle_forms(self):
        r = get_vehicle(self.active_vehicle_id)
        if not r:
            return

        self.veh_vars["nom"].set(r["nom"] or "")
        self.veh_vars["marque"].set(r["marque"] or "")
        self.veh_vars["modele"].set(r["modele"] or "")
        self.veh_vars["motorisation"].set(r["motorisation"] or "")
        self.veh_vars["energie"].set(r["energie"] or "")
        self.veh_vars["annee"].set("" if r["annee"] is None else str(r["annee"]))
        self.veh_vars["immatriculation"].set(r["immatriculation"] or "")
        self.veh_vars["dernier_km"].set(str(last_km_any(self.active_vehicle_id) or ""))

        img = _load_vehicle_photo_tk(r["photo_file"], max_w=288, max_h=176)
        self._veh_photo_img = img
        if img:
            self.veh_photo_label.config(image=img, text="")
        else:
            self.veh_photo_label.config(image="", text="(aucune photo)")
        # Préconisations constructeur (liées au véhicule actif)
        if hasattr(self, "preco_list"):
            try:
                self._refresh_preconisations()
            except Exception:
                pass


    # ---------- Pleins ----------
    def _build_pleins_tab(self):
        self.tab_pleins.columnconfigure(0, weight=1)

        header = ttk.Frame(self.tab_pleins)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Véhicule :").grid(row=0, column=0, sticky="w")
        self.pl_vehicle_var = tk.StringVar(value="")
        self.pl_vehicle_cb = ttk.Combobox(header, textvariable=self.pl_vehicle_var, state="readonly")
        self.pl_vehicle_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.pl_vehicle_cb.bind("<<ComboboxSelected>>", self._on_pl_vehicle_change)

        self.pl_header_label = ttk.Label(header, text="—", font=("TkDefaultFont", 11, "bold"))
        self.pl_header_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        box = ttk.Labelframe(self.tab_pleins, text="Pleins", padding=10)
        box.grid(row=1, column=0, sticky="nsew", pady=(10, 0))
        box.columnconfigure(0, weight=1)
        box.rowconfigure(0, weight=1)

        cols = ("id", "date", "km", "litres", "prix_litre", "total", "lieu")
        self.tree_pleins = ttk.Treeview(box, columns=cols, show="headings", height=12)
        self.tree_pleins.grid(row=0, column=0, sticky="nsew")

        headings = {"id": "ID", "date": "Date", "km": "Km", "litres": "Litres", "prix_litre": "Prix/L", "total": "Total", "lieu": "Lieu"}
        widths = {"id": 70, "date": 90, "km": 90, "litres": 90, "prix_litre": 90, "total": 90, "lieu": 420}
        for c in cols:
            self.tree_pleins.heading(c, text=headings[c])
            self.tree_pleins.column(c, width=widths[c], anchor="w", stretch=True)

        ysb = ttk.Scrollbar(box, orient="vertical", command=self.tree_pleins.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        xsb = ttk.Scrollbar(box, orient="horizontal", command=self.tree_pleins.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        self.tree_pleins.configure(yscroll=ysb.set, xscroll=xsb.set)

        actions = ttk.Frame(box)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Modifier", command=self._on_edit_plein).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Supprimer", command=self._on_delete_plein).grid(row=0, column=1)
        self.tree_pleins.bind("<Double-1>", lambda _e: self._on_edit_plein())

        form = ttk.Labelframe(self.tab_pleins, text="Plein effectué", padding=10)
        form.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        for c in range(6):
            form.columnconfigure(c, weight=1 if c in (1, 3, 5) else 0)

        ttk.Label(form, text="Date (JJMMAA) :").grid(row=0, column=0, sticky="w")
        self.new_pl_date = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_pl_date, width=12).grid(row=0, column=1, sticky="w", padx=(6, 12))

        ttk.Label(form, text="Km :").grid(row=0, column=2, sticky="w")
        self.new_pl_km = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_pl_km, width=10).grid(row=0, column=3, sticky="w", padx=(6, 12))

        ttk.Label(form, text="Litres :").grid(row=0, column=4, sticky="w")
        self.new_pl_litres = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_pl_litres, width=10).grid(row=0, column=5, sticky="w", padx=(6, 0))

        ttk.Label(form, text="Prix/L :").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.new_pl_prix = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_pl_prix, width=12).grid(row=1, column=1, sticky="w", padx=(6, 12), pady=(8, 0))

        ttk.Label(form, text="Total :").grid(row=1, column=2, sticky="w", pady=(8, 0))
        self.new_pl_total = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_pl_total, width=10).grid(row=1, column=3, sticky="w", padx=(6, 12), pady=(8, 0))

        ttk.Label(form, text="Lieu :").grid(row=1, column=4, sticky="w", pady=(8, 0))
        self.new_pl_lieu = tk.StringVar(value="")
        self.new_pl_lieu_cb = ttk.Combobox(form, textvariable=self.new_pl_lieu, values=[], state="normal")
        self.new_pl_lieu_cb.grid(row=1, column=5, sticky="ew", padx=(6, 0), pady=(8, 0))
        self.new_pl_lieu_cb.bind("<KeyRelease>", lambda e: _apply_autocomplete(self.new_pl_lieu_cb, self._pleins_lieux_all, self.new_pl_lieu.get()))

        ttk.Label(form, text="Astuce : laisse Total vide pour calcul auto (Litres × Prix/L).").grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))

        btn_row = ttk.Frame(form)
        btn_row.grid(row=2, column=5, sticky="ew", pady=(8, 0))
        btn_row.columnconfigure(0, weight=1)
        ttk.Button(btn_row, text="Enregistrer", command=self._on_add_plein).grid(row=0, column=0, sticky="ew")

    def _on_pl_vehicle_change(self, _evt=None):
        idx = self.pl_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._refresh_all_tabs_after_vehicle_change(source="pleins")

    def _selected_plein_id(self):
        sel = self.tree_pleins.selection()
        if not sel:
            return None
        vals = self.tree_pleins.item(sel[0], "values")
        try:
            return int(vals[0])
        except Exception:
            return None

    def _refresh_pleins(self):
        for item in self.tree_pleins.get_children():
            self.tree_pleins.delete(item)
        for r in list_pleins(self.active_vehicle_id):
            self.tree_pleins.insert("", "end", values=(
                int(r["id"]),
                _fmt_date(r["date_iso"]),
                r["km"] or "",
                _fmt_num(r["litres"], 2),
                _fmt_num(r["prix_litre"], 3),
                _fmt_num(r["total"], 2),
                r["lieu"] or "",
            ))

    def _refresh_pleins_lieux(self):
        try:
            self._pleins_lieux_all = list_pleins_lieux(self.active_vehicle_id)
        except Exception:
            self._pleins_lieux_all = []
        self.new_pl_lieu_cb["values"] = self._pleins_lieux_all

    def _on_add_plein(self):
        date_iso = _date_from_jjmmaa(self.new_pl_date.get().strip())
        if not date_iso:
            messagebox.showwarning("Date", "Date invalide (JJMMAA ou JJ/MM/AA).")
            return

        km = _safe_int(self.new_pl_km.get().strip().lower().replace("km", "").strip())
        if km is None or km < 0:
            messagebox.showwarning("Km", "Kilométrage invalide.")
            return

        litres = _safe_float(self.new_pl_litres.get().strip().replace(",", "."))
        if litres is None or litres <= 0:
            messagebox.showwarning("Litres", "Litres invalide.")
            return

        prix = _safe_float(self.new_pl_prix.get().strip().replace(",", "."))
        if prix is None or prix <= 0:
            messagebox.showwarning("Prix/L", "Prix/L invalide.")
            return

        total_in = self.new_pl_total.get().strip().replace(",", ".")
        if total_in:
            total = _safe_float(total_in)
            if total is None or total <= 0:
                messagebox.showwarning("Total", "Total invalide (ou laisse vide).")
                return
        else:
            total = litres * prix

        lieu = self.new_pl_lieu.get().strip()
        insert_plein(self.active_vehicle_id, date_iso, km, litres, prix, total, lieu)

        self._refresh_pleins()
        self._refresh_pleins_lieux()
        self._refresh_vehicle_forms()
        self._refresh_general_overview()
        self._set_status("Plein enregistré.")

        self.new_pl_date.set("")
        self.new_pl_km.set("")
        self.new_pl_litres.set("")
        self.new_pl_prix.set("")
        self.new_pl_total.set("")
        self.new_pl_lieu.set("")

    def _on_edit_plein(self):
        pid = self._selected_plein_id()
        if not pid:
            messagebox.showinfo("Sélection", "Sélectionne un plein dans la liste.")
            return

        def after_save():
            self._refresh_pleins()
            self._refresh_pleins_lieux()
            self._refresh_vehicle_forms()
            self._refresh_general_overview()
            self._set_status("Plein modifié.")

        PleinEditor(self, self.active_vehicle_id, pid, after_save)

    def _on_delete_plein(self):
        pid = self._selected_plein_id()
        if not pid:
            messagebox.showinfo("Sélection", "Sélectionne un plein dans la liste.")
            return
        if not messagebox.askyesno("Confirmer", "Supprimer ce plein ?"):
            return
        delete_plein(pid)
        self._refresh_pleins()
        self._refresh_pleins_lieux()
        self._refresh_vehicle_forms()
        self._refresh_general_overview()
        self._set_status("Plein supprimé.")

    # ---------- Entretiens ----------
    def _build_entretiens_tab(self):
        self.tab_ent.columnconfigure(0, weight=1)

        header = ttk.Frame(self.tab_ent)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Véhicule :").grid(row=0, column=0, sticky="w")
        self.ent_vehicle_var = tk.StringVar(value="")
        self.ent_vehicle_cb = ttk.Combobox(header, textvariable=self.ent_vehicle_var, state="readonly")
        self.ent_vehicle_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.ent_vehicle_cb.bind("<<ComboboxSelected>>", self._on_ent_vehicle_change)

        self.ent_header_label = ttk.Label(header, text="—", font=("TkDefaultFont", 11, "bold"))
        self.ent_header_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        box_type = ttk.Labelframe(self.tab_ent, text="Type d'entretien (pour ce véhicule)", padding=10)
        box_type.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for c in range(6):
            box_type.columnconfigure(c, weight=1 if c in (1, 3, 5) else 0)

        ttk.Label(box_type, text="Nom :").grid(row=0, column=0, sticky="w")
        self.type_name_var = tk.StringVar(value="")
        ttk.Entry(box_type, textvariable=self.type_name_var).grid(row=0, column=1, sticky="ew", padx=(6, 12))
        ttk.Button(box_type, text="Créer", command=self._on_type_create).grid(row=0, column=2, sticky="ew")
        ttk.Button(box_type, text="Modifier", command=self._on_type_update).grid(row=0, column=3, sticky="ew", padx=(10, 0))
        ttk.Button(box_type, text="Supprimer", command=self._on_type_delete).grid(row=0, column=4, sticky="ew", padx=(10, 0))

        ttk.Label(box_type, text="Fréquence :").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.type_km_var = tk.StringVar(value="")
        self.type_months_var = tk.StringVar(value="")
        ttk.Label(box_type, text="Km").grid(row=1, column=2, sticky="e", pady=(10, 0))
        ttk.Entry(box_type, textvariable=self.type_km_var, width=10).grid(row=1, column=3, sticky="w", padx=(6, 12), pady=(10, 0))
        ttk.Label(box_type, text="Mois").grid(row=1, column=4, sticky="e", pady=(10, 0))
        ttk.Entry(box_type, textvariable=self.type_months_var, width=8).grid(row=1, column=5, sticky="w", padx=(6, 0), pady=(10, 0))

        box_list = ttk.Frame(box_type)
        box_list.grid(row=2, column=0, columnspan=6, sticky="nsew", pady=(12, 0))
        box_list.columnconfigure(0, weight=1)

        self.tree_types = ttk.Treeview(box_list, columns=("rappel", "type", "freq"), show="headings", height=6)
        self.tree_types.grid(row=0, column=0, sticky="nsew")
        self.tree_types.heading("rappel", text="Rappel")
        self.tree_types.heading("type", text="Type d'entretien")
        self.tree_types.heading("freq", text="Fréquence de l'entretien")
        self.tree_types.column("rappel", width=70, anchor="center", stretch=False)
        self.tree_types.column("type", width=360, anchor="w", stretch=True)
        self.tree_types.column("freq", width=240, anchor="w", stretch=True)
        self.tree_types.bind("<<TreeviewSelect>>", self._on_type_select)
        self.tree_types.bind("<Button-1>", self._on_types_click)

        ysb_t = ttk.Scrollbar(box_list, orient="vertical", command=self.tree_types.yview)
        ysb_t.grid(row=0, column=1, sticky="ns")
        self.tree_types.configure(yscroll=ysb_t.set)

        list_box = ttk.Labelframe(self.tab_ent, text="Entretiens", padding=10)
        list_box.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        list_box.columnconfigure(0, weight=1)
        list_box.rowconfigure(0, weight=1)

        cols = ("id", "date", "km", "type", "kind", "cout", "by", "vbat", "details")
        self.tree_ent = ttk.Treeview(list_box, columns=cols, show="headings", height=10)
        self.tree_ent.grid(row=0, column=0, sticky="nsew")

        heads = {
            "id": "ID", "date": "Date", "km": "Km", "type": "Type d'entretien",
            "kind": "Type intervention", "cout": "Coût €", "by": "Effectué par", "vbat": "Vbat", "details": "Détails"
        }
        widths = {"id": 70, "date": 90, "km": 90, "type": 230, "kind": 170, "cout": 90, "by": 180, "vbat": 80, "details": 420}
        for c in cols:
            self.tree_ent.heading(c, text=heads[c])
            self.tree_ent.column(c, width=widths[c], anchor="w", stretch=True)

        ysb = ttk.Scrollbar(list_box, orient="vertical", command=self.tree_ent.yview)
        ysb.grid(row=0, column=1, sticky="ns")
        xsb = ttk.Scrollbar(list_box, orient="horizontal", command=self.tree_ent.xview)
        xsb.grid(row=1, column=0, sticky="ew")
        self.tree_ent.configure(yscroll=ysb.set, xscroll=xsb.set)

        actions = ttk.Frame(list_box)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        ttk.Button(actions, text="Modifier", command=self._on_edit_entretien).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(actions, text="Supprimer", command=self._on_delete_entretien).grid(row=0, column=1)
        self.tree_ent.bind("<Double-1>", lambda _e: self._on_edit_entretien())

        form = ttk.Labelframe(self.tab_ent, text="Entretien effectué", padding=10)
        form.grid(row=3, column=0, sticky="ew", pady=(12, 0))
        for c in range(6):
            form.columnconfigure(c, weight=1 if c in (1, 3, 5) else 0)

        ttk.Label(form, text="Date (JJMMAA) :").grid(row=0, column=0, sticky="w")
        self.new_date = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_date, width=12).grid(row=0, column=1, sticky="w", padx=(6, 12))

        ttk.Label(form, text="Km :").grid(row=0, column=2, sticky="w")
        self.new_km = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_km, width=10).grid(row=0, column=3, sticky="w", padx=(6, 12))

        ttk.Label(form, text="Intervention :").grid(row=0, column=4, sticky="w")
        self.new_kind = tk.StringVar(value="Entretien")
        ttk.Combobox(form, textvariable=self.new_kind, state="readonly",
                    values=["Réparation", "Entretien", "Entretien & Réparation"]).grid(row=0, column=5, sticky="ew", padx=(6, 0))

        ttk.Label(form, text="Type d'entretien :").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.new_type = tk.StringVar(value="")
        self.new_type_cb = ttk.Combobox(form, textvariable=self.new_type, state="readonly")
        self.new_type_cb.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(6, 12), pady=(8, 0))

        ttk.Label(form, text="Coût :").grid(row=1, column=3, sticky="w", pady=(8, 0))
        self.new_cost = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_cost, width=10).grid(row=1, column=4, sticky="w", padx=(6, 12), pady=(8, 0))

        ttk.Label(form, text="Effectué par :").grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.new_by = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_by).grid(row=2, column=1, columnspan=2, sticky="ew", padx=(6, 12), pady=(8, 0))

        ttk.Label(form, text="Tension Batterie (V) :").grid(row=2, column=3, sticky="w", pady=(8, 0))
        self.new_vbat = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_vbat, width=10).grid(row=2, column=4, sticky="w", padx=(6, 12), pady=(8, 0))

        ttk.Label(form, text="Détail :").grid(row=3, column=0, sticky="w", pady=(8, 0))
        self.new_details = tk.StringVar(value="")
        ttk.Entry(form, textvariable=self.new_details).grid(row=3, column=1, columnspan=4, sticky="ew", padx=(6, 12), pady=(8, 0))

        ttk.Button(form, text="Enregistrer l'entretien", command=self._on_add_entretien).grid(row=3, column=5, sticky="ew", pady=(8, 0))

    def _on_ent_vehicle_change(self, _evt=None):
        idx = self.ent_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._refresh_all_tabs_after_vehicle_change(source="entretiens")

    def _refresh_types_ui(self):
        self.selected_type_id = None
        self.type_name_var.set("")
        self.type_km_var.set("")
        self.type_months_var.set("")
        self._type_name_to_id = {}

        for item in self.tree_types.get_children():
            self.tree_types.delete(item)

        for r in list_vehicle_types(self.active_vehicle_id):
            type_id = int(r["type_id"])
            type_name = r["type_name"]
            freq = _format_frequency(r["period_km"], r["period_months"])
            enabled = 1
            try:
                enabled = int(r["enabled"]) if r["enabled"] is not None else 1
            except Exception:
                enabled = 1
            self.tree_types.insert("", "end", values=("☑" if enabled else "☐", type_name, freq))
            self._type_name_to_id[type_name] = type_id

    def _on_type_select(self, _evt=None):
        sel = self.tree_types.selection()
        if not sel:
            return
        vals = self.tree_types.item(sel[0], "values")
        chk, type_name, _freq = vals
        type_id = self._type_name_to_id.get(type_name)
        if not type_id:
            return
        self.selected_type_id = type_id

        # remplir champs
        conn = _connect_db()
        cur = conn.cursor()
        cur.execute("SELECT nom, period_km, period_months FROM entretien_types WHERE id=?", (int(type_id),))
        rr = cur.fetchone()
        conn.close()
        if rr:
            self.type_name_var.set(rr["nom"] or "")
            self.type_km_var.set("" if rr["period_km"] is None else str(rr["period_km"]))
            self.type_months_var.set("" if rr["period_months"] is None else str(rr["period_months"]))

        self.new_type.set(type_name)

    def _on_types_click(self, event):
        """Toggle checkbox 'Rappel' sur clic colonne 1."""
        region = self.tree_types.identify("region", event.x, event.y)
        if region != "cell":
            return
        col = self.tree_types.identify_column(event.x)  # '#1' = rappel
        if col != "#1":
            return
        row_id = self.tree_types.identify_row(event.y)
        if not row_id:
            return
        vals = list(self.tree_types.item(row_id, "values"))
        if len(vals) < 3:
            return
        chk, type_name, freq = vals[0], vals[1], vals[2]
        type_id = self._type_name_to_id.get(type_name)
        if not type_id:
            return

        enabled = 0 if str(chk).strip() in ("☑", "1", "True") else 1
        try:
            set_vehicle_type_enabled(self.active_vehicle_id, type_id, enabled)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return

        vals[0] = "☑" if enabled else "☐"
        self.tree_types.item(row_id, values=tuple(vals))

        # refresh UI/onglets impactés
        self._refresh_general_overview()
        self._refresh_types_ui()
        self._refresh_type_choices_for_new_entretien()
        self._set_status("Rappel " + ("activé" if enabled else "désactivé") + f" : {type_name}")

        return "break"

    def _on_type_create(self):
        name = self.type_name_var.get().strip()
        if not name:
            messagebox.showwarning("Nom manquant", "Entre un nom de type d'entretien.")
            return
        try:
            create_type_for_vehicle(self.active_vehicle_id, name, self.type_km_var.get().strip(), self.type_months_var.get().strip())
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._refresh_types_ui()
        self._refresh_type_choices_for_new_entretien()
        self._refresh_general_overview()
        self._set_status(f"Type créé : {name}")

    def _on_type_update(self):
        if not self.selected_type_id:
            messagebox.showinfo("Sélection", "Sélectionne un type dans la liste.")
            return
        name = self.type_name_var.get().strip()
        if not name:
            messagebox.showwarning("Nom manquant", "Entre un nom de type d'entretien.")
            return
        try:
            update_type(self.selected_type_id, name, self.type_km_var.get().strip(), self.type_months_var.get().strip())
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._refresh_types_ui()
        self._refresh_type_choices_for_new_entretien()
        self._refresh_general_overview()
        self._set_status("Type modifié.")

    def _on_type_delete(self):
        if not self.selected_type_id:
            messagebox.showinfo("Sélection", "Sélectionne un type dans la liste.")
            return
        if not messagebox.askyesno("Confirmer", "Supprimer ce type d'entretien de ce véhicule ?"):
            return
        try:
            delete_type_from_vehicle(self.active_vehicle_id, self.selected_type_id)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._refresh_types_ui()
        self._refresh_type_choices_for_new_entretien()
        self._refresh_general_overview()
        self._set_status("Type supprimé du véhicule.")

    def _refresh_type_choices_for_new_entretien(self):
        rows = list_vehicle_types(self.active_vehicle_id)
        names = [r["type_name"] for r in rows]
        self._type_name_to_id = {r["type_name"]: int(r["type_id"]) for r in rows}
        self.new_type_cb["values"] = names
        if names and self.new_type.get() not in names:
            self.new_type.set(names[0])
        if not names:
            self.new_type.set("")

    def _refresh_entretiens(self):
        for item in self.tree_ent.get_children():
            self.tree_ent.delete(item)
        for r in list_entretiens_full(self.active_vehicle_id):
            self.tree_ent.insert("", "end", values=(
                int(r["id"]),
                _fmt_date(r["date_iso"]),
                r["km"] or "",
                r["type_name"] or "",
                r["kind"] or "",
                _fmt_num(r["cout"], 2),
                r["performed_by"] or "",
                _fmt_num(r["battery_voltage"], 2),
                r["details"] or "",
            ))

    def _selected_entretien_id(self):
        sel = self.tree_ent.selection()
        if not sel:
            return None
        vals = self.tree_ent.item(sel[0], "values")
        try:
            return int(vals[0])
        except Exception:
            return None

    def _on_add_entretien(self):
        if not self._type_name_to_id:
            messagebox.showwarning("Types", "Aucun type d'entretien pour ce véhicule.")
            return

        date_iso = _date_from_jjmmaa(self.new_date.get().strip())
        if not date_iso:
            messagebox.showwarning("Date", "Date invalide.")
            return

        km = _safe_int(self.new_km.get().strip().lower().replace("km", "").strip())
        if km is None or km < 0:
            messagebox.showwarning("Km", "Kilométrage invalide.")
            return

        kind = self.new_kind.get().strip()
        if kind not in ("Réparation", "Entretien", "Entretien & Réparation"):
            kind = "Entretien"

        type_name = self.new_type.get().strip()
        type_id = self._type_name_to_id.get(type_name)
        if not type_id:
            messagebox.showwarning("Type", "Choisis un type d'entretien.")
            return

        cost_in = self.new_cost.get().strip().replace(",", ".")
        cout = None
        if cost_in:
            try:
                cout = float(cost_in)
            except Exception:
                messagebox.showwarning("Coût", "Coût invalide.")
                return

        by = self.new_by.get().strip()

        vbat_in = self.new_vbat.get().strip().replace(",", ".")
        vbat = None
        if vbat_in:
            try:
                vbat = float(vbat_in)
            except Exception:
                messagebox.showwarning("Vbat", "Valeur invalide.")
                return
            if not (5.00 <= vbat <= 25.99):
                messagebox.showwarning("Vbat", "Vbat doit être entre 5.00 et 25.99.")
                return

        details = self.new_details.get().strip()

        insert_entretien(self.active_vehicle_id, date_iso, km, kind, type_id, cout, by, details, vbat)
        self._refresh_entretiens()
        self._refresh_vehicle_forms()
        self._refresh_general_overview()
        self._set_status("Entretien enregistré.")

        self.new_date.set("")
        self.new_km.set("")
        self.new_cost.set("")
        self.new_by.set("")
        self.new_vbat.set("")
        self.new_details.set("")

    def _on_edit_entretien(self):
        eid = self._selected_entretien_id()
        if not eid:
            messagebox.showinfo("Sélection", "Sélectionne un entretien dans la liste.")
            return
        types = list_vehicle_types(self.active_vehicle_id)
        if not types:
            messagebox.showwarning("Types", "Aucun type d'entretien pour ce véhicule.")
            return

        type_choices = [t["type_name"] for t in types]
        type_name_to_id = {t["type_name"]: int(t["type_id"]) for t in types}

        def after_save():
            self._refresh_entretiens()
            self._refresh_vehicle_forms()
            self._refresh_general_overview()

        EntretienEditor(self, self.active_vehicle_id, eid, type_choices, type_name_to_id, after_save)

    def _on_delete_entretien(self):
        eid = self._selected_entretien_id()
        if not eid:
            messagebox.showinfo("Sélection", "Sélectionne un entretien dans la liste.")
            return
        if not messagebox.askyesno("Confirmer", "Supprimer cet entretien ?"):
            return
        delete_entretien(eid)
        self._refresh_entretiens()
        self._refresh_vehicle_forms()
        self._refresh_general_overview()
        self._set_status("Entretien supprimé.")

    # ---------- Refresh / Sync ----------
    def _refresh_all(self):
        self.vehicles_rows = list_vehicles()
        self._vehicle_index_to_id = []
        labels = []
        for r in self.vehicles_rows:
            vid = int(r["id"])
            nom = r["nom"] or f"Véhicule #{vid}"
            marque = r["marque"] or ""
            modele = r["modele"] or ""
            label = nom
            if marque or modele:
                label = f"{label} — {marque} {modele}".strip()
            labels.append(label)
            self._vehicle_index_to_id.append(vid)

        self.veh_vehicle_cb["values"] = labels
        self.pl_vehicle_cb["values"] = labels
        self.ent_vehicle_cb["values"] = labels

        self._refresh_all_tabs_after_vehicle_change(source="init")

    def _refresh_all_tabs_after_vehicle_change(self, source=""):
        try:
            idx = self._vehicle_index_to_id.index(self.active_vehicle_id)
        except ValueError:
            idx = 0
            self.active_vehicle_id = self._vehicle_index_to_id[0]

        if source != "vehicules":
            self.veh_vehicle_cb.current(idx)
        if source != "pleins":
            self.pl_vehicle_cb.current(idx)
        if source != "entretiens":
            self.ent_vehicle_cb.current(idx)

        r = get_vehicle(self.active_vehicle_id)
        title = f"Véhicule #{self.active_vehicle_id}"
        if r:
            title = r["nom"] or title
            if r["marque"] or r["modele"]:
                title = f"{title} — {(r['marque'] or '').strip()} {(r['modele'] or '').strip()}".rstrip()

        self.pl_header_label.config(text=title)
        self.ent_header_label.config(text=title)

        self._refresh_vehicle_forms()
        self._refresh_pleins()
        self._refresh_pleins_lieux()
        self._refresh_types_ui()
        self._refresh_type_choices_for_new_entretien()
        self._refresh_entretiens()
        self._refresh_general_overview()

        self._set_status(f"Véhicule #{self.active_vehicle_id} — DB: {os.path.basename(DB_FILE)}")


def main():
    app = GarageApp()
    app.mainloop()


if __name__ == "__main__":
    main()
