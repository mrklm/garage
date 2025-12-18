import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
from pathlib import Path
import shutil
import time
import datetime as _dt
import re

APP_NAME = "Garage"
APP_VERSION = "3.1.1"

SCRIPT_DIR = Path(__file__).resolve().parent
DB_FILE = str(SCRIPT_DIR / "garage.db")

ASSETS_DIR = SCRIPT_DIR / "assets"
VEHICLES_DIR = ASSETS_DIR / "vehicles"

MAX_VEHICLES = 5

# Utilisé uniquement pour fiabiliser le calcul de conso (si un plein a été oublié)
MISSED_FILL_KM_THRESHOLD = 1500

INTERVENTIONS = ["Réparation", "Entretien", "Entretien + Réparation"]

# Rappels (premiers items)
REMINDERS = [
    # Entretiens périodiques "classiques"
    {"key": "courroie", "label": "Courroie", "type": "km_years", "interval_km": 120_000, "interval_years": 5,
     "match_terms": ["courroie", "distribution"]},
    {"key": "vidange", "label": "Vidange", "type": "km_years", "interval_km": 20_000, "interval_years": 1,
     "match_terms": ["vidange"]},

    # Règles ajoutées (mensuel)
    {"key": "pneumatiques", "label": "Pneumatiques", "type": "monthly_simple", "interval_days": 30,
     "match_terms": ["pneumatiques", "pneus"],
     "ok_text": "Pneumatiques OK (à faire tout le mois)",
     "todo_text": "Pneumatiques à Vérifier"},
    {"key": "niveaux", "label": "Niveaux", "type": "monthly_simple", "interval_days": 30,
     "match_terms": ["niveaux"],
     "ok_text": "Niveaux OK (à faire tout le mois)",
     "todo_text": "Niveaux à Vérifier"},

    # Batterie (mensuel + interprétation)
    {"key": "batterie", "label": "Tension Batterie", "type": "battery_monthly", "interval_days": 30,
     "match_terms": ["tension de la batterie", "tension batterie"],
     "todo_text": "Vérifier la Tension de la Batterie"},

    # Contrôle technique (tous les 2 ans + alerte à 1 mois)
    {"key": "ct", "label": "Contrôle Technique", "type": "ct", "interval_years": 2, "imminent_days": 30,
     "match_terms": ["contrôle technique", "controle technique"]},
]


# ------------------- Prédictions (v3.1.x) -------------------
INFLATION_CUTOFF = _dt.date(2023, 1, 1)
INFLATION_FACTOR = 1.20

def _parse_iso_date(s):
    if s is None:
        return None
    if isinstance(s, _dt.date) and not isinstance(s, _dt.datetime):
        return s
    if isinstance(s, _dt.datetime):
        return s.date()
    if isinstance(s, str):
        try:
            return _dt.datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    return None

def _add_months(d: _dt.date, months: int) -> _dt.date:
    y = d.year + (d.month - 1 + months) // 12
    m = (d.month - 1 + months) % 12 + 1
    last_day = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m-1]
    return _dt.date(y, m, min(d.day, last_day))

def get_last_fuel_price_per_liter(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT prix_litre
        FROM pleins
        WHERE vehicule_id = ?
          AND prix_litre IS NOT NULL
        ORDER BY date DESC, id DESC
        LIMIT 1
        """,
        (vehicle_id,),
    )
    row = cur.fetchone()
    conn.close()
    if not row or row[0] is None:
        return None
    try:
        return float(row[0])
    except Exception:
        return None

def get_last_entretien_cost_and_date(vehicle_id: int, match_terms: list[str]):
    """
    Dernier coût + date d'un entretien dont (entretien_item OU precision) contient un des match_terms.
    """
    if not match_terms:
        return None, None

    conn = connect()
    cur = conn.cursor()

    # Construire une requête LIKE OR (case-insensitive)
    clauses = []
    params = [vehicle_id]
    for t in match_terms:
        clauses.append("(lower(entretien_item) LIKE ? OR lower(precision) LIKE ?)")
        tt = f"%{t.lower()}%"
        params.extend([tt, tt])

    sql = f"""
        SELECT cout, date
        FROM entretien
        WHERE vehicule_id = ?
          AND cout IS NOT NULL
          AND ({' OR '.join(clauses)})
        ORDER BY date DESC, id DESC
        LIMIT 1
    """
    cur.execute(sql, tuple(params))
    row = cur.fetchone()
    conn.close()

    if not row:
        return None, None

    try:
        cost = float(row[0]) if row[0] is not None else None
    except Exception:
        cost = None

    return cost, _parse_iso_date(row[1])

def predicted_entretien_cost_next_6_months(vehicle_id: int, horizon_months: int = 6) -> float:
    """
    Somme des coûts des entretiens à venir dans les X mois (fenêtre temporelle),
    basée sur le dernier coût connu pour le même entretien.
    +20% si la dernière occurrence est avant 2023.
    """
    today = _dt.date.today()
    horizon = _add_months(today, int(horizon_months))
    total = 0.0

    for r in REMINDERS:
        years = r.get("interval_years")
        if not years:
            # pas de règle temporelle -> on ne prédit pas ici
            continue

        match_terms = r.get("match_terms") or []
        cost, last_d = get_last_entretien_cost_and_date(vehicle_id, match_terms)
        if cost is None or last_d is None:
            continue

        # prochaine échéance par années
        try:
            next_due = last_d.replace(year=last_d.year + int(years))
        except ValueError:
            # 29 février etc.
            next_due = last_d.replace(month=2, day=28, year=last_d.year + int(years))

        if next_due <= horizon:
            if last_d < INFLATION_CUTOFF:
                cost *= INFLATION_FACTOR
            total += float(cost)

    return total
# Pillow optionnel (affichage images)
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont  # type: ignore
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


# -----------------------------
# Helpers
# -----------------------------

def safe_filename(name: str) -> str:
    name = (name or "").strip().lower()
    name = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    name = name.strip("_")
    return name or f"vehicule_{int(time.time())}"


def ensure_dirs():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    VEHICLES_DIR.mkdir(parents=True, exist_ok=True)
    gitkeep = VEHICLES_DIR / ".gitkeep"
    if not gitkeep.exists():
        try:
            gitkeep.write_text("", encoding="utf-8")
        except Exception:
            pass


def _try_parse_iso_date(s: str):
    try:
        y, m, d = s.split("-")
        return _dt.date(int(y), int(m), int(d))
    except Exception:
        return None


def _format_days(days: int) -> str:
    if days >= 0:
        return f"{days} j"
    return f"-{abs(days)} j"


def _format_km(km: int) -> str:
    return f"{km:,}".replace(",", " ").strip()


def load_photo_or_placeholder(photo_filename: str | None, size=(220, 150), label="Véhicule"):
    w, h = size
    path = (VEHICLES_DIR / photo_filename) if photo_filename else None

    if PIL_AVAILABLE:
        try:
            if path is None or not path.exists():
                raise FileNotFoundError("Photo introuvable")
            img = Image.open(path).convert("RGBA").resize((w, h))
            return ImageTk.PhotoImage(img), None
        except Exception as e:
            img = Image.new("RGBA", (w, h), (200, 200, 200, 255))
            draw = ImageDraw.Draw(img)
            draw.line((0, 0, w, h), fill=(150, 150, 150, 255), width=4)
            draw.line((0, h, w, 0), fill=(150, 150, 150, 255), width=4)
            text = f"{label}\nPhoto introuvable"
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
            bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.multiline_text(((w - tw) / 2, (h - th) / 2), text, fill=(60, 60, 60, 255), font=font, align="center")
            return ImageTk.PhotoImage(img), str(e)
    else:
        # Sans pillow on n'affiche pas d'image, on garde une zone grise
        return None, "Pillow non disponible"


# -----------------------------
# DB utils / migrations
# -----------------------------

def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def table_exists(conn, table: str) -> bool:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None


def table_columns(conn, table: str) -> list[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cur.fetchall()]


def ensure_vehicle(conn, nom: str, marque=None, modele=None, motorisation=None, energie=None, annee=None, immatriculation=None, photo_filename=None) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM vehicules WHERE nom = ?", (nom,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute(
        """
        INSERT INTO vehicules (nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename),
    )
    conn.commit()
    return int(cur.lastrowid)


def migrate_entretien_missing_id(conn: sqlite3.Connection):
    """
    Certains historiques ont une table entretien sans colonne id (ou avec schéma incomplet).
    On recrée une table propre et on recopie les données.
    """
    if not table_exists(conn, "entretien"):
        return
    cols = set(table_columns(conn, "entretien"))
    if "id" in cols:
        return

    cur = conn.cursor()
    cur.execute("BEGIN")
    # Table cible
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS entretien_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicule_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            kilometrage INTEGER,
            intervention TEXT NOT NULL,
            precision TEXT,
            entretien_item TEXT,
            effectue_par TEXT,
            cout REAL,
            FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE RESTRICT
        )
        """
    )

    # Détermine les colonnes disponibles à copier
    def col_or_null(name: str) -> str:
        return name if name in cols else "NULL"

    # Copie (sans id)
    cur.execute(
        f"""
        INSERT INTO entretien_new (vehicule_id, date, kilometrage, intervention, precision, entretien_item, effectue_par, cout)
        SELECT
            {col_or_null('vehicule_id')},
            {col_or_null('date')},
            {col_or_null('kilometrage')},
            {col_or_null('intervention')},
            {col_or_null('precision')},
            {col_or_null('entretien_item')},
            {col_or_null('effectue_par')},
            {col_or_null('cout')}
        FROM entretien
        """
    )

    cur.execute("DROP TABLE entretien")
    cur.execute("ALTER TABLE entretien_new RENAME TO entretien")
    conn.commit()


def init_db_and_migrate():
    ensure_dirs()
    conn = connect()
    cur = conn.cursor()

    # Véhicules
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            marque TEXT,
            modele TEXT,
            motorisation TEXT,
            energie TEXT,
            annee INTEGER,
            immatriculation TEXT,
            photo_filename TEXT
        )
        """
    )

    # Lieux
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lieux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )
        """
    )

    # Pleins
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS pleins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicule_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            kilometrage INTEGER NOT NULL,
            litres REAL NOT NULL,
            prix_litre REAL NOT NULL,
            total REAL NOT NULL,
            lieu TEXT,
            type_usage TEXT,
            commentaire TEXT,
            FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE RESTRICT
        )
        """
    )

    # Entretien (schéma cible)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS entretien (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicule_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            kilometrage INTEGER,
            intervention TEXT NOT NULL,
            precision TEXT,
            entretien_item TEXT,
            effectue_par TEXT,
            cout REAL,
            FOREIGN KEY(vehicule_id) REFERENCES vehicules(id) ON DELETE RESTRICT
        )
        """
    )

    # Catalogue entretien
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS entretien_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )
        """
    )

    # App config
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

    # Seeds
    cur.execute(
        """
        INSERT OR IGNORE INTO lieux (nom) VALUES
        ('St É'),
        ('Avranches'),
        ('Lille'),
        ('Pontorson'),
        ('Pleine Fougères');
        """
    )
    cur.execute(
        """
        INSERT OR IGNORE INTO entretien_items (nom) VALUES
        ('Vidange'),
        ('Filtres'),
        ('Pneus'),
        ('Freins'),
        ('Courroie'),
        ('Pneumatiques OK'),
        ('Niveaux OK'),
        ('Tension de la Batterie'),
        ('Contrôle Technique OK');
        """
    )
    conn.commit()

    # Migration: ancien champ pleins.vehicule -> vehicule_id
    cols_p = set(table_columns(conn, "pleins"))
    if "vehicule" in cols_p and "vehicule_id" not in cols_p:
        cur.execute("ALTER TABLE pleins ADD COLUMN vehicule_id INTEGER")
        conn.commit()

        biche_id = ensure_vehicle(conn, nom="Biche")
        titine_id = ensure_vehicle(conn, nom="Titine")

        cur.execute("UPDATE pleins SET vehicule_id = ? WHERE vehicule = 0", (biche_id,))
        cur.execute("UPDATE pleins SET vehicule_id = ? WHERE vehicule = 1", (titine_id,))
        cur.execute("UPDATE pleins SET vehicule_id = ? WHERE vehicule_id IS NULL", (biche_id,))
        conn.commit()

    # Migration: entretien sans id
    migrate_entretien_missing_id(conn)

    # Base vierge: 2 véhicules
    cur.execute("SELECT COUNT(*) FROM vehicules")
    if (cur.fetchone()[0] or 0) == 0:
        ensure_vehicle(conn, nom="Biche")
        ensure_vehicle(conn, nom="Titine")
        conn.commit()

    # Sécuriser vehicule_id non NULL
    cur.execute("SELECT COUNT(*) FROM pleins WHERE vehicule_id IS NULL")
    if (cur.fetchone()[0] or 0) > 0:
        cur.execute("SELECT id FROM vehicules ORDER BY id ASC LIMIT 1")
        first_id = int(cur.fetchone()[0])
        cur.execute("UPDATE pleins SET vehicule_id = ? WHERE vehicule_id IS NULL", (first_id,))
        conn.commit()

    conn.close()


def get_config(key: str) -> str | None:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT value FROM app_config WHERE key = ?", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_config(key: str, value: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO app_config(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value),
    )
    conn.commit()
    conn.close()


# -----------------------------
# DB: véhicules
# -----------------------------

def list_vehicles():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename
        FROM vehicules
        ORDER BY nom COLLATE NOCASE ASC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def get_vehicle(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename
        FROM vehicules
        WHERE id = ?
        """,
        (vehicle_id,),
    )
    row = cur.fetchone()
    conn.close()
    return row


def count_vehicles() -> int:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM vehicules")
    n = int(cur.fetchone()[0] or 0)
    conn.close()
    return n


def add_vehicle(nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vehicules (nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename),
    )
    conn.commit()
    new_id = int(cur.lastrowid)
    conn.close()
    return new_id


def update_vehicle(vehicle_id, nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE vehicules
        SET nom = ?, marque = ?, modele = ?, motorisation = ?, energie = ?, annee = ?, immatriculation = ?, photo_filename = ?
        WHERE id = ?
        """,
        (nom, marque, modele, motorisation, energie, annee, immatriculation, photo_filename, vehicle_id),
    )
    conn.commit()
    conn.close()


def delete_vehicle(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pleins WHERE vehicule_id = ?", (vehicle_id,))
    n1 = int(cur.fetchone()[0] or 0)
    cur.execute("SELECT COUNT(*) FROM entretien WHERE vehicule_id = ?", (vehicle_id,))
    n2 = int(cur.fetchone()[0] or 0)
    if n1 > 0 or n2 > 0:
        conn.close()
        raise ValueError(f"Suppression impossible : {n1} plein(s) et {n2} entretien(s) référencent ce véhicule.")
    cur.execute("DELETE FROM vehicules WHERE id = ?", (vehicle_id,))
    conn.commit()
    conn.close()


# -----------------------------
# DB: pleins
# -----------------------------

def last_km(vehicle_id: int, exclude_id=None):
    conn = connect()
    cur = conn.cursor()
    if exclude_id is None:
        cur.execute("SELECT MAX(kilometrage) FROM pleins WHERE vehicule_id = ?", (vehicle_id,))
    else:
        cur.execute(
            "SELECT MAX(kilometrage) FROM pleins WHERE vehicule_id = ? AND id <> ?",
            (vehicle_id, exclude_id),
        )
    res = cur.fetchone()
    conn.close()
    return int(res[0]) if res and res[0] is not None else None


def list_pleins(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, date, kilometrage, litres, prix_litre, total, lieu
        FROM pleins
        WHERE vehicule_id = ?
        ORDER BY date DESC, kilometrage DESC, id DESC
        """,
        (vehicle_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def list_pleins_km_asc(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, date, kilometrage, litres
        FROM pleins
        WHERE vehicule_id = ?
        ORDER BY kilometrage ASC, date ASC, id ASC
        """,
        (vehicle_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_plein(vehicle_id, date, kilometrage, litres, prix_litre, total, lieu):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pleins (vehicule_id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (vehicle_id, date, kilometrage, litres, prix_litre, total, lieu),
    )
    conn.commit()
    conn.close()


def update_plein(plein_id, vehicle_id, date, kilometrage, litres, prix_litre, total, lieu):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE pleins
        SET vehicule_id = ?, date = ?, kilometrage = ?, litres = ?, prix_litre = ?, total = ?, lieu = ?,
            type_usage = NULL, commentaire = NULL
        WHERE id = ?
        """,
        (vehicle_id, date, kilometrage, litres, prix_litre, total, lieu, plein_id),
    )
    conn.commit()
    conn.close()


def delete_plein(plein_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM pleins WHERE id = ?", (plein_id,))
    conn.commit()
    conn.close()


# -----------------------------
# DB: entretien
# -----------------------------

def list_entretien(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, date, kilometrage, intervention, precision, entretien_item, effectue_par, cout
        FROM entretien
        WHERE vehicule_id = ?
        ORDER BY date DESC, id DESC
        """,
        (vehicle_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_entretien(vehicle_id: int, date: str, kilometrage, intervention: str,
                  precision: str | None, entretien_item: str | None, effectue_par: str | None, cout):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO entretien (vehicule_id, date, kilometrage, intervention, precision, entretien_item, effectue_par, cout)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vehicle_id, date, kilometrage, intervention, precision, entretien_item, effectue_par, cout),
    )
    conn.commit()
    conn.close()


def update_entretien(entretien_id: int, vehicle_id: int, date: str, kilometrage, intervention: str,
                     precision: str | None, entretien_item: str | None, effectue_par: str | None, cout):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE entretien
        SET vehicule_id = ?, date = ?, kilometrage = ?, intervention = ?, precision = ?, entretien_item = ?, effectue_par = ?, cout = ?
        WHERE id = ?
        """,
        (vehicle_id, date, kilometrage, intervention, precision, entretien_item, effectue_par, cout, entretien_id),
    )
    conn.commit()
    conn.close()


def delete_entretien(entretien_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM entretien WHERE id = ?", (entretien_id,))
    conn.commit()
    conn.close()


def list_entretien_items():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT nom FROM entretien_items ORDER BY nom COLLATE NOCASE ASC")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def add_entretien_item(nom: str):
    nom = (nom or "").strip()
    if not nom:
        return
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO entretien_items (nom) VALUES (?)", (nom,))
    conn.commit()
    conn.close()


def find_last_maintenance_match(vehicle_id: int, match_terms: list[str]):
    terms = [t.strip().lower() for t in match_terms if (t or "").strip()]
    if not terms:
        return None

    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT date, kilometrage, entretien_item, precision
        FROM entretien
        WHERE vehicule_id = ?
        ORDER BY date DESC, id DESC
        """,
        (vehicle_id,),
    )
    rows = cur.fetchall()
    conn.close()

    for date_iso, km, item, prec in rows:
        hay = f"{item or ''} {prec or ''}".lower()
        if any(t in hay for t in terms):
            return date_iso, (int(km) if km is not None else None), (item or ""), (prec or "")
    return None


# -----------------------------
# DB: lieux
# -----------------------------

def list_lieux():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT nom FROM lieux ORDER BY nom COLLATE NOCASE ASC")
    rows = [r[0] for r in cur.fetchall()]
    conn.close()
    return rows


def add_lieu(nom: str):
    nom = (nom or "").strip()
    if not nom:
        return
    conn = connect()
    cur = conn.cursor()
    cur.execute("INSERT OR IGNORE INTO lieux (nom) VALUES (?)", (nom,))
    conn.commit()
    conn.close()


def count_pleins_for_lieu(nom: str) -> int:
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pleins WHERE lieu = ?", (nom,))
    n = int(cur.fetchone()[0] or 0)
    conn.close()
    return n


def delete_lieu(nom: str):
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM lieux WHERE nom = ?", (nom,))
    conn.commit()
    conn.close()


def rename_lieu(ancien: str, nouveau: str):
    ancien = (ancien or "").strip()
    nouveau = (nouveau or "").strip()
    if not ancien or not nouveau:
        raise ValueError("Ancien et nouveau nom doivent être renseignés.")
    if ancien == nouveau:
        return

    conn = connect()
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        cur.execute("UPDATE lieux SET nom = ? WHERE nom = ?", (nouveau, ancien))
        if cur.rowcount == 0:
            cur.execute("INSERT OR IGNORE INTO lieux (nom) VALUES (?)", (nouveau,))
        cur.execute("UPDATE pleins SET lieu = ? WHERE lieu = ?", (nouveau, ancien))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError(f"Le lieu '{nouveau}' existe déjà.")
    finally:
        conn.close()


# -----------------------------
# Calculs
# -----------------------------

def compute_avg_consumption_l_100_robust(vehicle_id: int, threshold_km: int = MISSED_FILL_KM_THRESHOLD):
    rows = list_pleins_km_asc(vehicle_id)
    if len(rows) < 2:
        return None

    km_valid = 0
    litres_valid = 0.0

    for i in range(1, len(rows)):
        km_prev = int(rows[i - 1][2])
        km_cur = int(rows[i][2])
        delta = km_cur - km_prev
        if delta <= 0:
            continue
        if delta > threshold_km:
            continue
        litres_i = float(rows[i][3])
        km_valid += delta
        litres_valid += litres_i

    if km_valid <= 0:
        return None
    return (litres_valid / km_valid) * 100.0


def _avg_per_year_from_records(dates: list[_dt.date], total_amount: float):
    if total_amount <= 0:
        return None
    if len(dates) < 2:
        return total_amount
    dmin, dmax = min(dates), max(dates)
    span_days = (dmax - dmin).days
    if span_days <= 0:
        return total_amount
    years = max(span_days / 365.25, 0.25)
    return total_amount / years


def compute_fuel_avg_per_year(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT date, total FROM pleins WHERE vehicule_id = ?", (vehicle_id,))
    rows = cur.fetchall()
    conn.close()
    dates = []
    total = 0.0
    for date_iso, amount in rows:
        d = _try_parse_iso_date(date_iso)
        if d:
            dates.append(d)
        try:
            total += float(amount or 0.0)
        except Exception:
            pass
    return _avg_per_year_from_records(dates, total)


def compute_maintenance_avg_per_year(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT date, cout FROM entretien WHERE vehicule_id = ?", (vehicle_id,))
    rows = cur.fetchall()
    conn.close()
    dates = []
    total = 0.0
    for date_iso, amount in rows:
        d = _try_parse_iso_date(date_iso)
        if d:
            dates.append(d)
        if amount is None:
            continue
        try:
            total += float(amount)
        except Exception:
            pass
    return _avg_per_year_from_records(dates, total)


def compute_reminders_status(vehicle_id: int):
    today = _dt.date.today()
    current_km = last_km(vehicle_id) or 0

    def _days_since(d: _dt.date) -> int:
        return (today - d).days

    def _safe_add_years(d: _dt.date, years: int) -> _dt.date:
        try:
            return d.replace(year=d.year + years)
        except ValueError:
            # gestion 29 février
            return d.replace(month=2, day=28, year=d.year + years)

    def _parse_voltage_from_text(text: str) -> float | None:
        # Accepte "12,5", "12.5", "12V5", "12,5V" etc.
        t = (text or "").strip().lower().replace(" ", "")
        if not t:
            return None
        # 12v5
        m = re.search(r"(?P<int>\d{2})v(?P<dec>\d)", t)
        if m:
            return float(f"{m.group('int')}.{m.group('dec')}")
        # 12,5 ou 12.5
        m = re.search(r"(\d{2})[\.,](\d)", t)
        if m:
            return float(f"{m.group(1)}.{m.group(2)}")
        # 12 (sans décimale)
        m = re.search(r"\b(\d{2})\b", t)
        if m:
            return float(m.group(1))
        return None

    def _battery_state(voltage: float) -> str:
        # Règles demandées
        if voltage <= 12.0:
            return "Tension en dessous de 12V : Attention décharge critique, prévoir remplacement"
        if 12.1 <= voltage <= 12.3:
            return "Tension de batterie faible : À recharger"
        if 12.4 <= voltage <= 12.5:
            return "Batterie limitte mais ça passe"
        # >= 12.6
        return "Batterie en bonne santé"

    results = []

    for r in REMINDERS:
        rtype = (r.get("type") or "km_years").strip()

        match = find_last_maintenance_match(vehicle_id, r.get("match_terms", []))

        # --- Mensuels simples (pneumatiques / niveaux)
        if rtype == "monthly_simple":
            if not match:
                results.append({"label": r["label"], "overdue": True, "message": r.get("todo_text") or "À faire", "display": r.get("todo_text") or "À faire"})
                continue

            last_date_iso, _last_km_value, _item, _prec = match
            last_date = _try_parse_iso_date(last_date_iso)
            if last_date is None:
                results.append({"label": r["label"], "overdue": True, "message": f"Date invalide: {last_date_iso}"})
                continue

            interval_days = int(r.get("interval_days", 30))
            ok = _days_since(last_date) <= interval_days
            results.append({
                "label": r["label"],
                "overdue": (not ok),
                "message": (r.get("ok_text") if ok else r.get("todo_text")) or "",
                "display": (r.get("ok_text") if ok else r.get("todo_text")) or ""
            })
            continue

        # --- Batterie (mensuel + interprétation)
        if rtype == "battery_monthly":
            if not match:
                results.append({"label": r["label"], "overdue": True, "message": r.get("todo_text") or "À faire", "display": r.get("todo_text") or "À faire"})
                continue

            last_date_iso, _last_km_value, item, prec = match
            last_date = _try_parse_iso_date(last_date_iso)
            if last_date is None:
                results.append({"label": r["label"], "overdue": True, "message": f"Date invalide: {last_date_iso}"})
                continue

            interval_days = int(r.get("interval_days", 30))
            overdue_month = _days_since(last_date) > interval_days
            if overdue_month:
                results.append({"label": r["label"], "overdue": True, "message": r.get("todo_text") or "À faire", "display": r.get("todo_text") or "À faire"})
                continue

            # Mesure récente -> interprétation de la tension
            v = _parse_voltage_from_text(f"{item} {prec}")
            if v is None:
                # Mesure non renseignée: on préfère alerter
                results.append({"label": r["label"], "overdue": True, "message": "Tension batterie non renseignée", "display": "Tension batterie non renseignée"})
                continue

            if v <= 12.0:
                disp = "Prévoir remplacement Batterie"
                is_bad = True
            elif 12.1 <= v <= 12.3:
                disp = "Batterie à recharger"
                is_bad = True
            elif 12.4 <= v <= 12.5:
                disp = "Tension batterie OK"
                is_bad = False
            else:
                disp = "Batterie en bonne santé"
                is_bad = False

            results.append({"label": r["label"], "overdue": is_bad, "message": disp, "display": disp})
            continue

        # --- Contrôle Technique (2 ans, + imminent à 1 mois)
        if rtype == "ct":
            if not match:
                results.append({"label": r["label"], "overdue": True, "message": "Contrôle Technique en retard", "display": "Contrôle Technique en retard"})
                continue

            last_date_iso, _last_km_value, _item, _prec = match
            last_date = _try_parse_iso_date(last_date_iso)
            if last_date is None:
                results.append({"label": r["label"], "overdue": True, "message": f"Date invalide: {last_date_iso}"})
                continue

            due_date = _safe_add_years(last_date, int(r.get("interval_years", 2)))
            due_str = due_date.strftime("%d/%m/%Y")
            days_left = (due_date - today).days

            if today > due_date:
                results.append({"label": r["label"], "overdue": True, "message": "Contrôle Technique en retard", "display": "Contrôle Technique en retard"})
            elif days_left <= int(r.get("imminent_days", 30)):
                results.append({"label": r["label"], "overdue": True, "message": f"Contrôle Technique imminent: {due_str}", "display": f"Contrôle Technique imminent: {due_str}"})
            else:
                results.append({"label": r["label"], "overdue": False, "message": f"Contrôle Technique OK prochain le {due_str}", "display": f"Contrôle Technique OK prochain le {due_str}"})
            continue

        # --- Par défaut: km + années (logique historique)
        if not match:
            results.append({"label": r["label"], "overdue": True, "message": "Aucun entretien enregistré"})
            continue

        last_date_iso, last_km_value, _item, _prec = match
        last_date = _try_parse_iso_date(last_date_iso)
        if last_date is None:
            results.append({"label": r["label"], "overdue": True, "message": f"Date invalide: {last_date_iso}"})
            continue

        due_km = None
        if last_km_value is not None and r.get("interval_km") is not None:
            due_km = int(last_km_value) + int(r["interval_km"])

        due_date = _safe_add_years(last_date, int(r.get("interval_years", 1)))
        overdue = (today > due_date) or ((due_km is not None) and (current_km >= due_km))
        due_date_str = due_date.strftime("%d/%m/%Y")

        if overdue:
            parts = []
            if due_km is not None:
                km_over = max(0, int(current_km) - int(due_km))
                parts.append(f"à faire depuis {_format_km(km_over)} KM")
            parts.append(f"le {due_date_str}")
            msg = " ou ".join(parts)
        else:
            parts = []
            if due_km is not None:
                km_left = max(0, int(due_km) - int(current_km))
                parts.append(f"à faire dans {_format_km(km_left)} KM")
            parts.append(f"le {due_date_str}")
            msg = ", ou ".join(parts) if len(parts) == 2 and parts[0].startswith("à faire") else " ou ".join(parts)

        results.append({"label": r["label"], "overdue": overdue, "message": msg})

    return results


# -----------------------------
# UI
# -----------------------------

class GarageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db_and_migrate()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1350x760")

        self.vehicle_id_active = None
        self.plein_edit_id = None
        self.entretien_edit_id = None
        self._battery_last_state_message = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_general = ttk.Frame(self.notebook)
        self.tab_pleins = ttk.Frame(self.notebook)
        self.tab_entretien = ttk.Frame(self.notebook)
        self.tab_options = ttk.Frame(self.notebook)
        self.tab_lieux = self.tab_options  # compat: ancien onglet "Lieux"
        self.tab_vehicules = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_general, text="Général")
        self.notebook.add(self.tab_entretien, text="Entretien")
        self.notebook.add(self.tab_pleins, text="Pleins")
        self.notebook.add(self.tab_vehicules, text="Véhicules")
        self.notebook.add(self.tab_options, text="Options")

        self._create_menu()
        self._build_general_tab()
        self._build_entretien_tab()
        self._build_pleins_tab()
        self._build_vehicules_tab()
        self._build_lieux_tab()  # contient la gestion des lieux + futurs réglages

        self._refresh_all_vehicles_ui()
        self._restore_active_vehicle()

    def _create_menu(self):
        menubar = tk.Menu(self)
        menu_aide = tk.Menu(menubar, tearoff=0)
        menu_aide.add_command(label="À propos…", command=self._about)
        menubar.add_cascade(label="Aide", menu=menu_aide)
        self.config(menu=menubar)

    def _about(self):
        messagebox.showinfo(
            "À propos",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "Suivi des pleins + entretien multi-véhicules + gestion des lieux.\n"
            "v3.0.1: onglet Général (vue flotte) + Pleins simplifié + Options.\n\n"
            f"Base: {DB_FILE}\n"
            f"Photos: {VEHICLES_DIR}\n"
            f"Pillow: {'OK' if PIL_AVAILABLE else 'non détecté'}",
        )


    # ------------------- Général -------------------

    def _build_general_tab(self):
        """Construit l'onglet Général (vue flotte)."""
        root = tk.Frame(self.tab_general)
        root.pack(fill=tk.BOTH, expand=True)

        # Canvas pour scroll horizontal si beaucoup de véhicules
        self.general_canvas = tk.Canvas(root, highlightthickness=0)
        self.general_canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        xscroll = ttk.Scrollbar(root, orient="horizontal", command=self.general_canvas.xview)
        xscroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.general_canvas.configure(xscrollcommand=xscroll.set)

        self.general_inner = tk.Frame(self.general_canvas)
        self.general_window = self.general_canvas.create_window((0, 0), window=self.general_inner, anchor="nw")

        self.general_cards = {}          # vehicle_id -> dict widgets
        self.general_photo_refs = {}     # vehicle_id -> PhotoImage (référence)
        self._general_vehicle_order = [] # ordre d'affichage

        def _on_inner_configure(event=None):
            self.general_canvas.configure(scrollregion=self.general_canvas.bbox("all"))

        def _on_canvas_configure(event):
            # Ajuste la largeur du "window" au canvas (hauteur libre, scroll sur X)
            self.general_canvas.itemconfigure(self.general_window, height=event.height)
            self._update_general_card_widths()

        self.general_inner.bind("<Configure>", _on_inner_configure)
        self.general_canvas.bind("<Configure>", _on_canvas_configure)

    def _update_general_card_widths(self):
        """Répartit l'espace en parts égales quand c'est possible."""
        if not hasattr(self, "general_canvas") or not hasattr(self, "general_inner"):
            return
        vids = getattr(self, "_general_vehicle_order", [])
        if not vids:
            return
        try:
            cw = int(self.general_canvas.winfo_width())
        except Exception:
            return
        # largeur mini pour rester lisible
        min_w = 380
        target = max(min_w, cw // max(1, len(vids)))
        for vid in vids:
            card = self.general_cards.get(vid, {}).get("card")
            if card is not None:
                card.configure(width=target)

    def _refresh_general_tab(self, vehicles_rows):
        """Reconstruit/rafraîchit toutes les cartes véhicules dans l'onglet Général."""
        if not hasattr(self, "general_inner"):
            return

        # Nettoyage si la flotte a changé
        wanted_ids = [int(r[0]) for r in vehicles_rows]
        existing_ids = set(self.general_cards.keys())

        for vid in list(existing_ids):
            if vid not in wanted_ids:
                try:
                    self.general_cards[vid]["card"].destroy()
                except Exception:
                    pass
                self.general_cards.pop(vid, None)
                self.general_photo_refs.pop(vid, None)

        # Construire les cartes manquantes, dans l'ordre
        self._general_vehicle_order = wanted_ids

        for col, row in enumerate(vehicles_rows):
            (vid, nom, marque, modele, motorisation, energie, annee, immat, photo_filename) = row
            vid = int(vid)

            if vid not in self.general_cards:
                card = tk.Frame(self.general_inner, bd=1, relief=tk.GROOVE)
                card.grid(row=0, column=col, sticky="nsew", padx=8, pady=8)
                card.grid_propagate(False)  # permet width fixe

                # Titre
                lbl_title = tk.Label(card, text=nom or "—", font=("Arial", 25, "bold"))
                lbl_title.pack(anchor="center", pady=(8, 6))

                top = tk.Frame(card)
                top.pack(fill=tk.X, padx=10)

                left = tk.Frame(top)
                left.pack(side=tk.LEFT, padx=(0, 10), anchor="n")

                right = tk.Frame(top)
                right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, anchor="n")

                # Photo
                canvas = tk.Canvas(left, width=220, height=150, highlightthickness=1)
                canvas.pack()


                # Infos véhicule (comme l'ancien onglet Pleins)
                tk.Label(right, text="Infos Véhicule", font=("Arial", 12, "bold", "underline")).pack(anchor="w")
                info = tk.Frame(right)
                info.pack(anchor="w", fill=tk.X, pady=(2, 6))

                lbl_marque = ttk.Label(info, text="")
                lbl_modele = ttk.Label(info, text="")
                lbl_motor = ttk.Label(info, text="")
                lbl_energie = ttk.Label(info, text="")
                lbl_annee = ttk.Label(info, text="")
                lbl_immat = ttk.Label(info, text="")

                for w in (lbl_marque, lbl_modele, lbl_motor, lbl_energie, lbl_annee, lbl_immat):
                    w.pack(anchor="w")

                # Bloc sous les infos véhicule : KM / coûts + prédictions (v3.1.1)
                below_info = tk.Frame(card)
                below_info.pack(fill=tk.X, padx=10, pady=(6, 0))

                # Ligne KM + dépenses 6 mois
                row_km = tk.Frame(below_info)
                row_km.pack(fill=tk.X, pady=(2, 0))

                lbl_km = tk.Label(row_km, text="— km", font=("Arial", 20, "bold"), anchor="w")
                lbl_km.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

                lbl_pred6 = tk.Label(row_km, text="Dépenses à prévoir dans les 6 mois: —", anchor="e")
                lbl_pred6.config(font=lbl_km.cget("font"))
                lbl_pred6.pack(side=tk.RIGHT, padx=(12, 0))

                # Ligne carburant moy/an + prix carburant actuel
                row_fuel = tk.Frame(below_info)
                row_fuel.pack(fill=tk.X, pady=(2, 0))

                lbl_fuel = tk.Label(row_fuel, text="Carburant (moy/an): —", font=("Arial", 13, "bold"), anchor="w")
                lbl_fuel.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

                lbl_last_price = tk.Label(row_fuel, text="Prix carburant actuel: — €/L", anchor="e")
                lbl_last_price.config(font=lbl_fuel.cget("font"))
                lbl_last_price.pack(side=tk.RIGHT, padx=(12, 0))

                # Ligne entretien moy/an + coûts à venir
                row_maint = tk.Frame(below_info)
                row_maint.pack(fill=tk.X, pady=(2, 0))

                lbl_maint = tk.Label(row_maint, text="Entretien (moy/an): —", font=("Arial", 13, "bold"), anchor="w")
                lbl_maint.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

                lbl_pred_maint = tk.Label(row_maint, text="Coûts des entretiens à venir: — €", anchor="e")
                lbl_pred_maint.config(font=lbl_maint.cget("font"))
                lbl_pred_maint.pack(side=tk.RIGHT, padx=(12, 0))

                # Alertes/rappels
                alerts = tk.Frame(card)
                alerts.pack(fill=tk.BOTH, expand=True, padx=10, pady=(8, 10))

                tk.Label(alerts, text="- - - Entretiens - - -", font=("Arial", 20, "bold",)).pack(anchor="center")
                reminder_lines = []
                for _ in range(len(REMINDERS)):
                    lbl = tk.Label(alerts, text="—", font=("Arial", 18), anchor="w", justify="left")
                    lbl.pack(anchor="w")
                    reminder_lines.append(lbl)

                # clic = sélectionner véhicule actif
                def _make_onclick(v=vid):
                    return lambda e=None: self._on_vehicle_set_active(v)

                card.bind("<Button-1>", _make_onclick())
                for child in card.winfo_children():
                    child.bind("<Button-1>", _make_onclick())

                self.general_cards[vid] = {
                    "card": card,
                    "title": lbl_title,
                    "canvas": canvas,
                    "lbl_km": lbl_km,
                    "lbl_fuel": lbl_fuel,
                    "lbl_maint": lbl_maint,
                    "lbl_pred6": lbl_pred6,
                    "lbl_last_price": lbl_last_price,
                    "lbl_pred_maint": lbl_pred_maint,
                    "lbl_marque": lbl_marque,
                    "lbl_modele": lbl_modele,
                    "lbl_motor": lbl_motor,
                    "lbl_energie": lbl_energie,
                    "lbl_annee": lbl_annee,
                    "lbl_immat": lbl_immat,
                    "reminders": reminder_lines,
                }

            # (re)positionner la carte (au cas où l'ordre change)
            self.general_cards[vid]["card"].grid(row=0, column=col, sticky="nsew", padx=8, pady=8)
            self.general_inner.grid_columnconfigure(col, weight=1, uniform="fleet")

            # Rafraîchir contenu (photo, km, coûts, infos, alertes)
            widgets = self.general_cards[vid]

            widgets["title"].config(text=nom or "—")

            photo_img, _err = load_photo_or_placeholder(photo_filename, size=(220, 150), label=nom or "Véhicule")
            widgets["canvas"].delete("all")
            widgets["canvas"].create_image(0, 0, image=photo_img, anchor="nw")
            self.general_photo_refs[vid] = photo_img  # garder référence

            km = last_km(vid) or 0
            widgets["lbl_km"].config(text=f"{int(km):,} km".replace(",", " "))

            fuel = compute_fuel_avg_per_year(vid)
            maint = compute_maintenance_avg_per_year(vid)
            fuel = 0.0 if fuel is None else float(fuel)
            maint = 0.0 if maint is None else float(maint)

            widgets["lbl_fuel"].config(text=f"Carburant (moy/an): {fuel:,.0f} €".replace(",", " "))
            widgets["lbl_maint"].config(text=f"Entretien (moy/an): {maint:,.0f} €".replace(",", " "))


            # Prédictions (6 mois)
            last_price = get_last_fuel_price_per_liter(vid)
            pred_maint = predicted_entretien_cost_next_6_months(vid, horizon_months=6)

            if last_price is None:
                widgets["lbl_last_price"].config(text="Prix carburant actuel: — €/L")
            else:
                widgets["lbl_last_price"].config(text=f"Prix carburant actuel: {last_price:.3f} €/L")

            widgets["lbl_pred_maint"].config(text=f"Coûts des entretiens à venir: {pred_maint:,.0f} €".replace(",", " "))

            pred_total = float(pred_maint)
            widgets["lbl_pred6"].config(text=f"Coût 6 prochains mois: {pred_total:,.0f} €".replace(",", " "))

            widgets["lbl_marque"].config(text=f"Marque : {marque or '—'}")
            widgets["lbl_modele"].config(text=f"Modèle : {modele or '—'}")
            widgets["lbl_motor"].config(text=f"Motorisation : {motorisation or '—'}")
            widgets["lbl_energie"].config(text=f"Énergie : {energie or '—'}")
            widgets["lbl_annee"].config(text=f"Année : {annee or '—'}")
            widgets["lbl_immat"].config(text=f"Immat. : {immat or '—'}")

            statuses = compute_reminders_status(vid)
            for i, st in enumerate(statuses):
                line = st.get("display") or f"{st['label']}: {st['message']}"
                symbol = "✗ " if st.get("overdue") else "✓ "
                txt = f"{symbol}{line}"
                if i < len(widgets["reminders"]):
                    widgets["reminders"][i].config(text=txt, fg=("red" if st.get("overdue") else "green"))

        self._update_general_card_widths()

    # ------------------- Pleins -------------------

    def _build_pleins_tab(self):
        top = tk.Frame(self.tab_pleins)
        top.pack(fill=tk.X, pady=10)

        # LEFT: véhicule + photo + km + coûts
        left = tk.Frame(top)
        left.pack(side=tk.LEFT, padx=20)

        tk.Label(left, text="Véhicule").pack(anchor="w")
        self.cb_vehicle = ttk.Combobox(left, state="readonly", width=26)
        self.cb_vehicle.pack(anchor="w")
        self.cb_vehicle.bind("<<ComboboxSelected>>", self._on_vehicle_selected_from_combo)

        self.canvas_photo = tk.Canvas(left, width=220, height=150, highlightthickness=1)
        self.canvas_photo.pack(pady=6)

        self.lbl_km = tk.Label(left, text="— km", font=("Arial", 24, "bold"), anchor="center")
        self.lbl_km.pack(fill=tk.X)

        # Coûts moyens/an sous KM
        self.lbl_fuel_year = tk.Label(left, text="Carburant (moy/an): —", font=("Arial", 17, "bold"), anchor="center")
        self.lbl_fuel_year.pack(fill=tk.X, pady=(6, 0))
        self.lbl_maint_year = tk.Label(left, text="Entretien (moy/an): —", font=("Arial", 17, "bold"), anchor="center")
        self.lbl_maint_year.pack(fill=tk.X, pady=(2, 0))

        # CENTER: boutons + rappels (centrés sous les boutons)
        center = tk.Frame(top)
        center.pack(side=tk.LEFT, expand=True, fill=tk.X)

        buttons = tk.Frame(center)
        buttons.pack()

        tk.Button(buttons, text="Ajouter / Enregistrer", command=self._on_save_plein, width=28).pack(pady=4)
        tk.Button(buttons, text="Modifier le plein sélectionné", command=self._on_load_selected_plein, width=28).pack(pady=4)
        tk.Button(buttons, text="Supprimer le plein sélectionné", command=self._on_delete_selected_plein, width=28).pack(pady=4)
        tk.Button(buttons, text="Importer un fichier (CSV)", command=self._import_csv, width=28).pack(pady=4)

        self.reminders_big_frame = tk.Frame(center)
        # v3: rappels déplacés dans l'onglet "Général"
        self.reminder_big_lines = []

        # RIGHT: infos véhicule
        right = tk.Frame(top)
        # v3: infos véhicule déplacées dans l'onglet "Général"
        # (on conserve les widgets pour compat, mais on ne les affiche pas ici)

        tk.Label(right, text="Infos Véhicule", font=("Arial", 14, "bold", "underline")).pack(anchor="w")
        self.info_lines_frame = tk.Frame(right)
        self.info_lines_frame.pack(anchor="w", fill=tk.X)

        self.lbl_info_marque = ttk.Label(self.info_lines_frame, text="")
        self.lbl_info_modele = ttk.Label(self.info_lines_frame, text="")
        self.lbl_info_motorisation = ttk.Label(self.info_lines_frame, text="")
        self.lbl_info_energie = ttk.Label(self.info_lines_frame, text="")
        self.lbl_info_annee = ttk.Label(self.info_lines_frame, text="")
        self.lbl_info_immat = ttk.Label(self.info_lines_frame, text="")
        self.lbl_info_conso = ttk.Label(self.info_lines_frame, text="")

        for w in [
            self.lbl_info_marque, self.lbl_info_modele, self.lbl_info_motorisation, self.lbl_info_energie,
            self.lbl_info_annee, self.lbl_info_immat, self.lbl_info_conso
        ]:
            w.pack(anchor="w")

        # TABLE
        mid = tk.Frame(self.tab_pleins)
        mid.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ("id", "date", "km", "litres", "prix", "total", "lieu")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings")

        widths = {"id": 55, "date": 90, "km": 90, "litres": 120, "prix": 90, "total": 90, "lieu": 220}
        headings = {"id": "ID", "date": "Date", "km": "Km", "litres": "Nbre de Litres", "prix": "€ / Litre",
                    "total": "Total (€)", "lieu": "Lieu"}

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], stretch=(col == "lieu"))

        self.tree.pack(fill=tk.BOTH, expand=True)

        # FORM
        form = tk.Frame(self.tab_pleins)
        form.pack(fill=tk.X, padx=10, pady=10)

        self.plein_entries = {}
        fields = [
            ("Jour", "jour", 6),
            ("Mois", "mois", 6),
            ("Année", "annee", 6),
            ("Km", "km", 10),
            ("Nbre de Litres", "litres", 12),
            ("€ / Litre", "prix", 12),
            ("Lieu", "lieu", 22),
        ]

        for i, (label, key, width) in enumerate(fields):
            tk.Label(form, text=label, font=("Arial", 12, "bold") if key == "prix" else None).grid(row=0, column=i, padx=4)
            if key == "lieu":
                cb = ttk.Combobox(form, state="readonly", width=width)
                cb.grid(row=1, column=i, padx=4)
                self.plein_entries[key] = cb
            else:
                e = tk.Entry(form, width=width)
                e.grid(row=1, column=i, padx=4)
                self.plein_entries[key] = e

        self._refresh_lieux_combo()

    def _import_csv(self):
        messagebox.showinfo("Importer CSV", "Fonction à venir.")

    # ------------------- Entretien -------------------

    def _build_entretien_tab(self):
        top = tk.Frame(self.tab_entretien)
        top.pack(fill=tk.X, pady=10, padx=10)

        left = tk.Frame(top)
        left.pack(side=tk.LEFT, padx=10)

        tk.Label(left, text="Véhicule").pack(anchor="w")
        self.cb_vehicle_ent = ttk.Combobox(left, state="readonly", width=26)
        self.cb_vehicle_ent.pack(anchor="w")
        self.cb_vehicle_ent.bind("<<ComboboxSelected>>", self._on_vehicle_selected_from_combo_entretien)

        btns = tk.Frame(top)
        btns.pack(side=tk.LEFT, padx=30)
        tk.Button(btns, text="Ajouter / Enregistrer", command=self._on_save_entretien, width=24).pack(pady=4)
        tk.Button(btns, text="Modifier sélection", command=self._on_load_selected_entretien, width=24).pack(pady=4)
        tk.Button(btns, text="Supprimer sélection", command=self._on_delete_selected_entretien, width=24).pack(pady=4)

        mid = tk.Frame(self.tab_entretien)
        mid.pack(fill=tk.BOTH, expand=True, padx=10)

        cols = ("id", "date", "km", "intervention", "detail", "effectue_par", "cout")
        self.tree_ent = ttk.Treeview(mid, columns=cols, show="headings")
        widths = {"id": 55, "date": 90, "km": 90, "intervention": 170, "detail": 420, "effectue_par": 220, "cout": 90}
        heads = {"id": "ID", "date": "Date", "km": "Km", "intervention": "Intervention", "detail": "Détail", "effectue_par": "Effectué par", "cout": "€"}

        for c in cols:
            self.tree_ent.heading(c, text=heads[c])
            self.tree_ent.column(c, width=widths[c], stretch=(c in ("detail", "effectue_par")))

        self.tree_ent.pack(fill=tk.BOTH, expand=True)

        form = tk.Frame(self.tab_entretien)
        form.pack(fill=tk.X, padx=10, pady=10)

        self.ent_entries = {}
        # Ligne 1 : date + km + intervention
        for i, (lab, key, w) in enumerate([("Jour", "jour", 6), ("Mois", "mois", 6), ("Année", "annee", 6)]):
            tk.Label(form, text=lab).grid(row=0, column=i, padx=4, sticky="w")
            e = tk.Entry(form, width=w)
            e.grid(row=1, column=i, padx=4, sticky="w")
            self.ent_entries[key] = e

        tk.Label(form, text="Km").grid(row=0, column=3, padx=4, sticky="w")
        e_km = tk.Entry(form, width=10)
        e_km.grid(row=1, column=3, padx=4, sticky="w")
        self.ent_entries["km"] = e_km

        tk.Label(form, text="Intervention").grid(row=0, column=4, padx=4, sticky="w")
        cb_int = ttk.Combobox(form, state="readonly", width=22, values=INTERVENTIONS)
        cb_int.grid(row=1, column=4, padx=4, sticky="w")
        cb_int.bind("<<ComboboxSelected>>", self._on_ent_intervention_changed)
        self.ent_entries["intervention"] = cb_int

        # Tension batterie (##V#) - activée uniquement si l'entretien sélectionné est "Tension de la Batterie"
        tk.Label(form, text="Tension Batterie").grid(row=0, column=5, padx=4, sticky="w")
        e_bi = tk.Entry(form, width=4)
        e_bi.grid(row=1, column=5, padx=2, sticky="w")
        tk.Label(form, text="V").grid(row=1, column=6, padx=2, sticky="w")
        e_bd = tk.Entry(form, width=3)
        e_bd.grid(row=1, column=7, padx=2, sticky="w")
        self.ent_entries["batt_i"] = e_bi
        self.ent_entries["batt_d"] = e_bd

        # Ligne 2 : détails + acteur + coût (réparti sur 2 lignes pour éviter le débordement)
        tk.Label(form, text="Préciser (réparation)").grid(row=2, column=0, columnspan=3, padx=4, sticky="w")
        e_prec = tk.Entry(form, width=46)
        e_prec.grid(row=3, column=0, columnspan=3, padx=4, sticky="we")
        self.ent_entries["precision"] = e_prec

        tk.Label(form, text="Entretien").grid(row=2, column=3, padx=4, sticky="w")
        cb_item = ttk.Combobox(form, state="readonly", width=22)
        cb_item.grid(row=3, column=3, padx=4, sticky="w")
        cb_item.bind("<<ComboboxSelected>>", self._on_entretien_item_changed)
        self.ent_entries["entretien_item"] = cb_item
        cb_item.bind("<<ComboboxSelected>>", self._on_entretien_item_selected)

        tk.Button(
            form,
            text="Ajouter un type d'entretien",
            command=self._add_entretien_item_dialog
        ).grid(row=3, column=4, padx=4, sticky="w")

        tk.Label(form, text="Effectué par").grid(row=2, column=5, padx=4, sticky="w")
        e_par = tk.Entry(form, width=22)
        e_par.grid(row=3, column=5, padx=4, sticky="w")
        self.ent_entries["effectue_par"] = e_par

        tk.Label(form, text="€").grid(row=2, column=6, padx=4, sticky="w")
        e_eur = tk.Entry(form, width=10)
        e_eur.grid(row=3, column=6, padx=4, sticky="w")
        self.ent_entries["cout"] = e_eur

        self._refresh_entretien_items_combo()
        self._set_entretien_mode("Entretien + Réparation")
        self._update_battery_fields_state()

    def _refresh_entretien_items_combo(self):
        items = list_entretien_items()
        cb: ttk.Combobox = self.ent_entries["entretien_item"]
        cur = cb.get()
        cb["values"] = items
        cb.set(cur if cur in items else (items[0] if items else ""))

    def _add_entretien_item_dialog(self):
        nom = simpledialog.askstring("Ajouter un entretien", "Nom (ex: vidange, pneus...) :")
        if not nom:
            return
        add_entretien_item(nom)
        self._refresh_entretien_items_combo()
        self._refresh_vehicle_photo_and_info()

    def _on_ent_intervention_changed(self, _evt=None):
        mode = self.ent_entries["intervention"].get() or "Entretien + Réparation"
        self._set_entretien_mode(mode)

    def _set_entretien_mode(self, mode: str):
        mode = (mode or "").strip()
        if mode not in INTERVENTIONS:
            mode = "Entretien + Réparation"
        self.ent_entries["intervention"].set(mode)

        e_prec: tk.Entry = self.ent_entries["precision"]
        cb_item: ttk.Combobox = self.ent_entries["entretien_item"]

        if mode == "Réparation":
            e_prec.configure(state="normal")
            cb_item.configure(state="disabled")
        elif mode == "Entretien":
            e_prec.configure(state="disabled")
            cb_item.configure(state="readonly")
        else:
            e_prec.configure(state="normal")
            cb_item.configure(state="readonly")

        self._update_battery_fields_state()

    
    def _on_entretien_item_changed(self, _evt=None):
        self._update_battery_fields_state()

    def _update_battery_fields_state(self):
        # Active les champs tension uniquement pour l'entretien "Tension de la Batterie"
        mode = (self.ent_entries.get("intervention").get() or "").strip()
        item = (self.ent_entries.get("entretien_item").get() or "").strip().lower()

        enable = (mode in ("Entretien", "Entretien + Réparation")) and (item == "tension de la batterie")
        for k in ("batt_i", "batt_d"):
            w = self.ent_entries.get(k)
            if not w:
                continue
            w.configure(state=("normal" if enable else "disabled"))
            if not enable:
                w.delete(0, tk.END)

    def _on_entretien_item_selected(self, _evt=None):
        """Gestion des items d'entretien nécessitant une saisie guidée.

        Désormais, la tension batterie se saisit directement dans le formulaire.
        """
        return


    def _open_battery_voltage_dialog(self):
        win = tk.Toplevel(self.root)
        win.title("Tension de la Batterie")
        win.resizable(False, False)
        win.transient(self.root)
        win.update_idletasks()
        win.deiconify()
        win.after(50, win.grab_set)

        info = (
            "Si la tension moteur éteint est entre 12,6 et 12,8V, la batterie est en bonne santé ; "
            "12,4V, acceptable ; 12,2V à recharger ; 12,0V ou moins, décharge critique"
        )
        tk.Label(win, text=info, wraplength=520, justify="left").pack(padx=14, pady=(12, 8), anchor="w")
        tk.Label(win, text="Entrez le résultat de la mesure de tension de la batterie", justify="left").pack(
            padx=14, pady=(0, 10), anchor="w"
        )

        row = tk.Frame(win)
        row.pack(padx=14, pady=(0, 10), anchor="w")

        e_int = tk.Entry(row, width=2, justify="center")
        e_int.pack(side=tk.LEFT)
        tk.Label(row, text="V").pack(side=tk.LEFT, padx=6)
        e_dec = tk.Entry(row, width=1, justify="center")
        e_dec.pack(side=tk.LEFT)

        # pré-remplissage utile
        e_int.insert(0, "12")
        e_dec.insert(0, "6")

        def _state(voltage: float) -> str:
            if voltage <= 12.0:
                return "Tension en dessous de 12V : Attention décharge critique, prévoir remplacement"
            if 12.1 <= voltage <= 12.3:
                return "Tension de batterie faible : À Recharger"
            if 12.4 <= voltage <= 12.5:
                return "Batterie OK"
            return "Batterie en bonne santé"

        def _on_ok():
            try:
                i = (e_int.get() or "").strip()
                d = (e_dec.get() or "").strip()
                if len(i) != 2 or not i.isdigit():
                    raise ValueError("Le premier champ doit contenir 2 chiffres (ex: 12).")
                if len(d) != 1 or not d.isdigit():
                    raise ValueError("Le second champ doit contenir 1 chiffre (ex: 6).")
                v = float(f"{int(i)}.{int(d)}")
            except Exception as ex:
                messagebox.showerror("Tension de la Batterie", str(ex))
                return

            msg = _state(v)
            v_str = f"{v:.1f}".replace(".", ",")
            cb_item: ttk.Combobox = self.ent_entries.get("entretien_item")
            if cb_item:
                cb_item.set(f"Tension de la Batterie {v_str}V")
            # On met le message dans le champ "Effectué par" si vide ? Non.
            # On laisse l'utilisateur enregistrer, l'info est dans l'intitulé.
            self._battery_last_state_message = msg  # utilisé au moment de l'enregistrement
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(padx=14, pady=(0, 12), anchor="e")
        tk.Button(btns, text="Annuler", command=win.destroy, width=12).pack(side=tk.RIGHT, padx=(6, 0))
        tk.Button(btns, text="Valider", command=_on_ok, width=12).pack(side=tk.RIGHT)

    def _format_entretien_detail(self, intervention: str, precision: str | None, entretien_item: str | None) -> str:
        precision = (precision or "").strip()
        entretien_item = (entretien_item or "").strip()

        if intervention == "Réparation":
            return precision
        if intervention == "Entretien":
            return entretien_item if not precision else f"{entretien_item} — {precision}"

        parts = []
        if entretien_item:
            parts.append(f"Entretien: {entretien_item}")
        if precision:
            parts.append(f"Réparation: {precision}")
        return " | ".join(parts)

    def _refresh_entretien(self):
        for item in self.tree_ent.get_children():
            self.tree_ent.delete(item)
        if not self.vehicle_id_active:
            return
        rows = list_entretien(int(self.vehicle_id_active))
        for (eid, date_iso, km, intervention, precision, entretien_item, effectue_par, cout) in rows:
            try:
                an, mois, jour = date_iso.split("-")
                date_aff = f"{jour}/{mois}/{an[2:]}"
            except Exception:
                date_aff = date_iso
            detail = self._format_entretien_detail(intervention, precision, entretien_item)
            cout_str = "" if cout is None else f"{float(cout):.2f}"
            km_str = "" if km is None else str(int(km))
            self.tree_ent.insert("", "end", values=(eid, date_aff, km_str, intervention, detail, effectue_par or "", cout_str))

    def _clear_entretien_form(self):
        for k in ("jour", "mois", "annee", "km", "precision", "effectue_par", "cout", "batt_i", "batt_d"):
            self.ent_entries[k].delete(0, tk.END)
        self.ent_entries["intervention"].set("Entretien + Réparation")
        self._set_entretien_mode("Entretien + Réparation")
        self._refresh_entretien_items_combo()

    def _on_save_entretien(self):
        if not self.vehicle_id_active:
            messagebox.showwarning("Véhicule", "Aucun véhicule sélectionné.")
            return
        try:
            j = int((self.ent_entries["jour"].get() or "0").strip())
            m = int((self.ent_entries["mois"].get() or "0").strip())
            a = int((self.ent_entries["annee"].get() or "0").strip())
            if not (1 <= j <= 31 and 1 <= m <= 12 and 0 <= a <= 99):
                raise ValueError("Date invalide : Jour 1-31, Mois 1-12, Année sur 2 chiffres.")
            date_iso = f"20{a:02d}-{m:02d}-{j:02d}"

            km_txt = (self.ent_entries["km"].get() or "").strip()
            km = None
            if km_txt:
                km = int(km_txt)
                if km < 0:
                    raise ValueError("Km entretien invalide (doit être positif).")

            intervention = (self.ent_entries["intervention"].get() or "").strip()
            if intervention not in INTERVENTIONS:
                raise ValueError("Intervention invalide.")

            precision = (self.ent_entries["precision"].get() or "").strip() or None
            

            entretien_item = (self.ent_entries["entretien_item"].get() or "").strip() or None

            if intervention == "Réparation":
                if not precision:
                    raise ValueError("Pour une réparation, précise ce qui a été réparé.")
                entretien_item = None
            elif intervention == "Entretien":
                if not entretien_item:
                    raise ValueError("Pour un entretien, sélectionne un élément dans la liste.")
                precision = None
            else:
                if not precision and not entretien_item:
                    raise ValueError("Renseigne au moins un type d’entretien et/ou une réparation.")

            # Cas spécial: Tension batterie -> interprétation depuis les champs "Tension Batterie"
            if entretien_item and entretien_item.strip().lower() == "tension de la batterie":
                bi = (self.ent_entries.get("batt_i").get() or "").strip() if self.ent_entries.get("batt_i") else ""
                bd = (self.ent_entries.get("batt_d").get() or "").strip() if self.ent_entries.get("batt_d") else ""
                if not (bi.isdigit() and len(bi) in (1, 2) and bd.isdigit() and len(bd) == 1):
                    raise ValueError("Renseigne la tension batterie au format ##V# (ex: 12V6).")
                v = float(f"{int(bi)}.{int(bd)}")

                # Interprétation demandée (messages courts pour les alertes)
                if v <= 12.0:
                    batt_msg = "Prévoir remplacement batterie"
                elif 12.1 <= v <= 12.3:
                    batt_msg = "Batterie à recharger"
                elif 12.4 <= v <= 12.5:
                    batt_msg = "Tension batterie OK"
                else:
                    batt_msg = "Batterie en bonne santé"

                # On stocke la mesure dans "precision" (sans polluer la liste déroulante)
                precision = (precision or None)
                stored = f"{v:.1f}V — {batt_msg}".replace(".", ",")
                precision = stored

                # ne pas ajouter dans entretien_items (sinon on accumule des variantes)
            elif entretien_item and entretien_item.lower().startswith("tension de la batterie"):
                # Compatibilité: anciennes entrées
                pass
            elif entretien_item:
                add_entretien_item(entretien_item)

            # reset (évite de réutiliser l'état précédent par erreur)
            self._battery_last_state_message = None

            effectue_par = (self.ent_entries["effectue_par"].get() or "").strip() or None

            cout_txt = (self.ent_entries["cout"].get() or "").strip()
            cout = None
            if cout_txt:
                cout = float(cout_txt.replace(",", "."))

            if self.entretien_edit_id is None:
                add_entretien(int(self.vehicle_id_active), date_iso, km, intervention, precision, entretien_item, effectue_par, cout)
            else:
                update_entretien(int(self.entretien_edit_id), int(self.vehicle_id_active), date_iso, km, intervention, precision, entretien_item, effectue_par, cout)
                self.entretien_edit_id = None

            self._refresh_entretien()
            self._clear_entretien_form()
            self._refresh_vehicle_photo_and_info()
            self._refresh_stats()

        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _on_load_selected_entretien(self):
        sel = self.tree_ent.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Sélectionne une ligne à modifier.")
            return
        values = self.tree_ent.item(sel, "values")
        self.entretien_edit_id = int(values[0])

        conn = connect()
        cur = conn.cursor()
        cur.execute(
            "SELECT date, kilometrage, intervention, precision, entretien_item, effectue_par, cout FROM entretien WHERE id = ?",
            (int(self.entretien_edit_id),),
        )
        row = cur.fetchone()
        conn.close()
        if not row:
            return

        date_iso, km, intervention, precision, entretien_item, effectue_par, cout = row
        try:
            an, mois, jour = date_iso.split("-")
        except Exception:
            messagebox.showerror("Erreur", f"Date invalide en base: {date_iso}")
            return

        self._clear_entretien_form()
        self.ent_entries["jour"].insert(0, jour)
        self.ent_entries["mois"].insert(0, mois)
        self.ent_entries["annee"].insert(0, an[2:])

        if km is not None:
            self.ent_entries["km"].insert(0, str(int(km)))

        self.ent_entries["intervention"].set(intervention)
        self._set_entretien_mode(intervention)

        if precision:
            self.ent_entries["precision"].insert(0, precision)
        if entretien_item:
            self._refresh_entretien_items_combo()
            self.ent_entries["entretien_item"].set(entretien_item)

        if effectue_par:
            self.ent_entries["effectue_par"].insert(0, effectue_par)
        if cout is not None:
            self.ent_entries["cout"].insert(0, f"{float(cout):.2f}")

    def _on_delete_selected_entretien(self):
        sel = self.tree_ent.selection()
        if not sel:
            return
        eid = int(self.tree_ent.item(sel, "values")[0])
        if not messagebox.askyesno("Confirmation", f"Supprimer l'entretien ID {eid} ?"):
            return
        delete_entretien(eid)
        self.entretien_edit_id = None
        self._battery_last_state_message = None
        self._refresh_entretien()
        self._clear_entretien_form()
        self._refresh_vehicle_photo_and_info()
        self._refresh_stats()

    # ------------------- Lieux -------------------

    def _build_lieux_tab(self):
        container = tk.Frame(self.tab_lieux)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        col_list = tk.Frame(container)
        col_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        col_actions = tk.Frame(container)
        col_actions.pack(side=tk.LEFT, padx=30, fill=tk.Y)

        tk.Label(col_list, text="Liste des lieux :").pack(anchor="w")
        self.listbox_lieux = tk.Listbox(col_list, height=22)
        self.listbox_lieux.pack(fill=tk.BOTH, expand=True, pady=5)

        tk.Button(col_actions, text="Ajouter un lieu…", command=self._on_add_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col_actions, text="Supprimer le lieu sélectionné", command=self._on_delete_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col_actions, text="Renommer le lieu sélectionné…", command=self._on_rename_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col_actions, text="Rafraîchir", command=self._refresh_lieux_ui).pack(fill=tk.X, pady=15)

        self._refresh_lieux_ui()

    def _refresh_lieux_combo(self):
        lieux = list_lieux()
        cb: ttk.Combobox = self.plein_entries["lieu"]
        cur = cb.get()
        cb["values"] = lieux
        cb.set(cur if cur in lieux else "")

    def _refresh_lieux_ui(self):
        lieux = list_lieux()
        self.listbox_lieux.delete(0, tk.END)
        for nom in lieux:
            self.listbox_lieux.insert(tk.END, nom)
        self._refresh_lieux_combo()

    def _on_add_lieu(self):
        nom = simpledialog.askstring("Ajouter un lieu", "Nom du lieu :")
        if not nom:
            return
        add_lieu(nom)
        self._refresh_lieux_ui()

    def _on_delete_lieu(self):
        sel = self.listbox_lieux.curselection()
        if not sel:
            return
        nom = self.listbox_lieux.get(sel[0])
        n = count_pleins_for_lieu(nom)
        if n > 0:
            messagebox.showwarning(
                "Suppression impossible",
                f"Le lieu '{nom}' est utilisé dans {n} plein(s).\n\n"
                "Pour corriger une faute d’orthographe, utilise « Renommer… ».",
            )
            return
        if not messagebox.askyesno("Confirmation", f"Supprimer '{nom}' ?"):
            return
        delete_lieu(nom)
        self._refresh_lieux_ui()

    def _on_rename_lieu(self):
        sel = self.listbox_lieux.curselection()
        if not sel:
            return
        ancien = self.listbox_lieux.get(sel[0])
        nouveau = simpledialog.askstring("Renommer un lieu", f"Nouveau nom pour '{ancien}' :")
        if nouveau is None:
            return
        nouveau = nouveau.strip()
        if not nouveau:
            messagebox.showwarning("Renommer", "Le nouveau nom ne peut pas être vide.")
            return
        try:
            rename_lieu(ancien, nouveau)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self._refresh_lieux_ui()

    # ------------------- Véhicules -------------------

    def _build_vehicules_tab(self):
        container = tk.Frame(self.tab_vehicules)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = tk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = tk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=30)

        tk.Label(left, text=f"Véhicules (max {MAX_VEHICLES}) :").pack(anchor="w")
        self.tree_vehicles = ttk.Treeview(left, columns=("id", "nom", "marque", "modele", "annee", "energie"), show="headings")
        for c, w in [("id", 50), ("nom", 150), ("marque", 130), ("modele", 130), ("annee", 70), ("energie", 110)]:
            self.tree_vehicles.heading(c, text=c.upper())
            self.tree_vehicles.column(c, width=w, stretch=(c == "nom"))
        self.tree_vehicles.pack(fill=tk.BOTH, expand=True, pady=6)
        self.tree_vehicles.bind("<<TreeviewSelect>>", self._on_vehicle_row_selected)

        self.vehicle_form = {}
        form = tk.Frame(right)
        form.pack(fill=tk.X)

        def add_field(label, key, row, width=26):
            tk.Label(form, text=label).grid(row=row, column=0, sticky="w", pady=3)
            e = tk.Entry(form, width=width)
            e.grid(row=row, column=1, pady=3)
            self.vehicle_form[key] = e

        add_field("Nom (pseudo)", "nom", 0)
        add_field("Marque", "marque", 1)
        add_field("Modèle", "modele", 2)
        add_field("Motorisation", "motorisation", 3)
        add_field("Énergie", "energie", 4)
        add_field("Année", "annee", 5)
        add_field("Immatriculation", "immat", 6)

        tk.Label(form, text="Photo").grid(row=7, column=0, sticky="w", pady=3)
        self.lbl_photo = tk.Label(form, text="(aucune)")
        self.lbl_photo.grid(row=7, column=1, sticky="w", pady=3)
        tk.Button(form, text="Choisir…", command=self._pick_vehicle_photo).grid(row=8, column=1, sticky="w", pady=3)

        self.canvas_vehicle_preview = tk.Canvas(right, width=240, height=160, highlightthickness=1)
        self.canvas_vehicle_preview.pack(pady=10)

        actions = tk.Frame(right)
        actions.pack(fill=tk.X, pady=10)

        tk.Button(actions, text="Ajouter", command=self._on_vehicle_add, width=18).grid(row=0, column=0, pady=4, padx=4)
        tk.Button(actions, text="Enregistrer", command=self._on_vehicle_save, width=18).grid(row=0, column=1, pady=4, padx=4)
        tk.Button(actions, text="Supprimer", command=self._on_vehicle_delete, width=18).grid(row=1, column=0, pady=4, padx=4)
        tk.Button(actions, text="Définir actif", command=self._on_vehicle_set_active, width=18).grid(row=1, column=1, pady=4, padx=4)
        tk.Button(actions, text="Rafraîchir", command=self._refresh_all_vehicles_ui, width=18).grid(row=2, column=0, pady=4, padx=4)

        self._vehicle_selected_id = None
        self._vehicle_selected_photo_filename = None
        self._clear_vehicle_form()

    def _restore_active_vehicle(self):
        vehicles = list_vehicles()
        if not vehicles:
            conn = connect()
            ensure_vehicle(conn, nom="Véhicule 1")
            conn.close()
            vehicles = list_vehicles()

        saved = get_config("active_vehicle_id")
        saved_id = int(saved) if saved and saved.isdigit() else None
        existing_ids = {int(v[0]) for v in vehicles}

        if saved_id in existing_ids:
            self.vehicle_id_active = saved_id
        else:
            self.vehicle_id_active = int(vehicles[0][0])

        self._refresh_vehicle_selectors()
        self._apply_active_vehicle_to_ui()

    def _refresh_vehicle_selectors(self):
        vehicles = list_vehicles()
        display = [row[1] for row in vehicles]
        self._vehicle_name_to_id = {row[1]: int(row[0]) for row in vehicles}

        self.cb_vehicle["values"] = display
        self.cb_vehicle_ent["values"] = display

        current_name = None
        for name, vid in self._vehicle_name_to_id.items():
            if vid == self.vehicle_id_active:
                current_name = name
                break
        if current_name is None and display:
            current_name = display[0]
            self.vehicle_id_active = self._vehicle_name_to_id[current_name]

        if current_name:
            self.cb_vehicle.set(current_name)
            self.cb_vehicle_ent.set(current_name)

    def _on_vehicle_selected_from_combo(self, _evt=None):
        name = self.cb_vehicle.get()
        vid = self._vehicle_name_to_id.get(name)
        if vid is None:
            return
        self._set_active_vehicle(vid)

    def _on_vehicle_selected_from_combo_entretien(self, _evt=None):
        name = self.cb_vehicle_ent.get()
        vid = self._vehicle_name_to_id.get(name)
        if vid is None:
            return
        self._set_active_vehicle(vid)

    def _set_active_vehicle(self, vid: int):
        self.vehicle_id_active = int(vid)
        set_config("active_vehicle_id", str(self.vehicle_id_active))

        self.plein_edit_id = None
        self.entretien_edit_id = None
        self._battery_last_state_message = None

        self._clear_plein_form()
        self._clear_entretien_form()

        self._refresh_vehicle_selectors()
        self._apply_active_vehicle_to_ui()

    def _apply_active_vehicle_to_ui(self):
        self._refresh_vehicle_photo_and_info()
        self._refresh_pleins()
        self._refresh_km_label()
        self._refresh_entretien()
        self._refresh_stats()

    def _refresh_stats(self):
        if not self.vehicle_id_active:
            self.lbl_fuel_year.config(text="Carburant (moy/an): —")
            self.lbl_maint_year.config(text="Entretien (moy/an): —")
            return

        fuel = compute_fuel_avg_per_year(int(self.vehicle_id_active))
        maint = compute_maintenance_avg_per_year(int(self.vehicle_id_active))

        self.lbl_fuel_year.config(text=f"Carburant (moy/an): {fuel:,.0f} €".replace(",", " ") if fuel is not None else "Carburant (moy/an): —")
        self.lbl_maint_year.config(text=f"Entretien (moy/an): {maint:,.0f} €".replace(",", " ") if maint is not None else "Entretien (moy/an): —")

    def _refresh_vehicle_photo_and_info(self):
        v = get_vehicle(int(self.vehicle_id_active)) if self.vehicle_id_active else None
        if not v:
            return
        _, nom, marque, modele, motorisation, energie, annee, immat, photo = v

        self.canvas_photo.delete("all")
        tk_img, _err = load_photo_or_placeholder(photo, size=(220, 150), label=nom)
        self._tk_vehicle_photo = tk_img
        if tk_img is not None:
            self.canvas_photo.create_image(0, 0, anchor="nw", image=tk_img)
        else:
            self.canvas_photo.create_rectangle(0, 0, 220, 150, fill="#c8c8c8", outline="#999999")
            self.canvas_photo.create_text(110, 75, text=f"{nom}\nPhoto introuvable", justify="center")

        self.lbl_info_marque.config(text=f"Marque : {marque}" if marque else "")
        self.lbl_info_modele.config(text=f"Modèle : {modele}" if modele else "")
        self.lbl_info_motorisation.config(text=f"Motorisation : {motorisation}" if motorisation else "")
        self.lbl_info_energie.config(text=f"Énergie : {energie}" if energie else "")
        self.lbl_info_annee.config(text=f"Année : {annee}" if annee else "")
        self.lbl_info_immat.config(text=f"Immatriculation : {immat}" if immat else "")

        conso = compute_avg_consumption_l_100_robust(int(self.vehicle_id_active))
        self.lbl_info_conso.config(text=f"Conso moyenne : {conso:.2f} L/100" if conso is not None else "Conso moyenne : —")

        statuses = compute_reminders_status(int(self.vehicle_id_active))
        for i, st in enumerate(statuses):
            # Si compute_reminders_status fournit déjà une ligne prête, on l'utilise.
            line = st.get("display") or f"{st['label']}: {st['message']}"
            symbol = "✗ " if st.get("overdue") else "✓ "
            txt = f"{symbol}{line}"
            if i < len(self.reminder_big_lines):
                self.reminder_big_lines[i].config(text=txt, fg=("red" if st.get("overdue") else "green"))

    def _refresh_km_label(self):
        km = last_km(int(self.vehicle_id_active)) if self.vehicle_id_active else None
        self.lbl_km.config(text=f"{km if km is not None else '—'} km")

    # --- Pleins CRUD ---

    def _refresh_pleins(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.vehicle_id_active:
            return
        rows = list_pleins(int(self.vehicle_id_active))
        for (pid, date_iso, km, litres, prix, total, lieu) in rows:
            try:
                an, mois, jour = date_iso.split("-")
                date_aff = f"{jour}/{mois}/{an[2:]}"
            except Exception:
                date_aff = date_iso
            self.tree.insert("", "end", values=(pid, date_aff, km, f"{litres:.2f}", f"{prix:.3f}", f"{total:.2f}", lieu or ""))

    def _clear_plein_form(self):
        for w in self.plein_entries.values():
            if isinstance(w, ttk.Combobox):
                w.set("")
            else:
                w.delete(0, tk.END)

    def _on_save_plein(self):
        if not self.vehicle_id_active:
            messagebox.showwarning("Véhicule", "Aucun véhicule sélectionné.")
            return
        try:
            j = int((self.plein_entries["jour"].get() or "0").strip())
            m = int((self.plein_entries["mois"].get() or "0").strip())
            a = int((self.plein_entries["annee"].get() or "0").strip())
            if not (1 <= j <= 31 and 1 <= m <= 12 and 0 <= a <= 99):
                raise ValueError("Date invalide : Jour 1-31, Mois 1-12, Année sur 2 chiffres.")
            date_iso = f"20{a:02d}-{m:02d}-{j:02d}"

            km = int(self.plein_entries["km"].get())
            last = last_km(int(self.vehicle_id_active), exclude_id=self.plein_edit_id)
            if last is not None and km < last:
                raise ValueError(f"Kilométrage incohérent : {km} km < dernier relevé ({last} km).")

            litres = float(self.plein_entries["litres"].get().replace(",", "."))
            prix = float(self.plein_entries["prix"].get().replace(",", "."))
            total = litres * prix
            lieu = (self.plein_entries["lieu"].get() or "").strip()

            if self.plein_edit_id is None:
                add_plein(int(self.vehicle_id_active), date_iso, km, litres, prix, total, lieu)
            else:
                update_plein(int(self.plein_edit_id), int(self.vehicle_id_active), date_iso, km, litres, prix, total, lieu)
                self.plein_edit_id = None

            self._refresh_pleins()
            self._refresh_vehicle_photo_and_info()
            self._refresh_km_label()
            self._refresh_stats()
            self._clear_plein_form()

        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def _on_load_selected_plein(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Sélectionne un plein à modifier.")
            return
        values = self.tree.item(sel, "values")
        self.plein_edit_id = int(values[0])

        date_val = str(values[1])
        try:
            jour, mois, an = date_val.split("/")
        except Exception:
            messagebox.showerror("Erreur", f"Format de date invalide : {date_val}")
            return

        self._clear_plein_form()
        self.plein_entries["jour"].insert(0, jour)
        self.plein_entries["mois"].insert(0, mois)
        self.plein_entries["annee"].insert(0, an)
        self.plein_entries["km"].insert(0, values[2])
        self.plein_entries["litres"].insert(0, values[3])
        self.plein_entries["prix"].insert(0, values[4])
        self.plein_entries["lieu"].set(values[6])

    def _on_delete_selected_plein(self):
        sel = self.tree.selection()
        if not sel:
            return
        pid = int(self.tree.item(sel, "values")[0])
        if not messagebox.askyesno("Confirmation", f"Supprimer le plein ID {pid} ?"):
            return
        delete_plein(pid)
        self.plein_edit_id = None
        self._refresh_pleins()
        self._refresh_vehicle_photo_and_info()
        self._refresh_km_label()
        self._refresh_stats()
        self._clear_plein_form()

    # ---------------- Véhicules: gestion ----------------

    def _refresh_all_vehicles_ui(self):
        for item in self.tree_vehicles.get_children():
            self.tree_vehicles.delete(item)

        vehicles = list_vehicles()
        # Met à jour la vue "Général" (vue flotte)
        if hasattr(self, "_refresh_general_tab"):
            self._refresh_general_tab(vehicles)
        for (vid, nom, marque, modele, motorisation, energie, annee, immat, photo) in vehicles:
            self.tree_vehicles.insert("", "end", values=(vid, nom, marque or "", modele or "", annee or "", energie or ""))

        if vehicles and self.vehicle_id_active is None:
            self.vehicle_id_active = int(vehicles[0][0])

        self._refresh_vehicle_selectors()
        if self.vehicle_id_active is not None:
            self._apply_active_vehicle_to_ui()

    def _on_vehicle_row_selected(self, _evt=None):
        sel = self.tree_vehicles.selection()
        if not sel:
            return
        values = self.tree_vehicles.item(sel, "values")
        vid = int(values[0])
        self._vehicle_selected_id = vid

        v = get_vehicle(vid)
        if not v:
            return
        _, nom, marque, modele, motorisation, energie, annee, immat, photo = v
        self._vehicle_selected_photo_filename = photo

        self.vehicle_form["nom"].delete(0, tk.END); self.vehicle_form["nom"].insert(0, nom or "")
        self.vehicle_form["marque"].delete(0, tk.END); self.vehicle_form["marque"].insert(0, marque or "")
        self.vehicle_form["modele"].delete(0, tk.END); self.vehicle_form["modele"].insert(0, modele or "")
        self.vehicle_form["motorisation"].delete(0, tk.END); self.vehicle_form["motorisation"].insert(0, motorisation or "")
        self.vehicle_form["energie"].delete(0, tk.END); self.vehicle_form["energie"].insert(0, energie or "")
        self.vehicle_form["annee"].delete(0, tk.END); self.vehicle_form["annee"].insert(0, str(annee) if annee else "")
        self.vehicle_form["immat"].delete(0, tk.END); self.vehicle_form["immat"].insert(0, immat or "")

        self._update_vehicle_photo_labels_and_preview(photo)

    def _update_vehicle_photo_labels_and_preview(self, photo_filename):
        self.lbl_photo.config(text=photo_filename or "(aucune)")
        self.canvas_vehicle_preview.delete("all")
        name = self.vehicle_form["nom"].get().strip() or "Véhicule"
        tk_img, _err = load_photo_or_placeholder(photo_filename, size=(240, 160), label=name)
        self._tk_vehicle_preview = tk_img
        if tk_img is not None:
            self.canvas_vehicle_preview.create_image(0, 0, anchor="nw", image=tk_img)
        else:
            self.canvas_vehicle_preview.create_rectangle(0, 0, 240, 160, fill="#c8c8c8", outline="#999999")
            self.canvas_vehicle_preview.create_text(120, 80, text=f"{name}\nPhoto introuvable", justify="center")

    def _clear_vehicle_form(self):
        self._vehicle_selected_id = None
        self._vehicle_selected_photo_filename = None
        for w in self.vehicle_form.values():
            w.delete(0, tk.END)
        self._update_vehicle_photo_labels_and_preview(None)

    def _pick_vehicle_photo(self):
        path = filedialog.askopenfilename(
            title="Choisir une photo",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp *.bmp"), ("Tous fichiers", "*.*")],
        )
        if not path:
            return
        src = Path(path)
        if not src.exists():
            messagebox.showerror("Photo", "Fichier introuvable.")
            return

        name_hint = safe_filename(self.vehicle_form["nom"].get())
        ext = src.suffix.lower() if src.suffix else ".png"
        dest_name = f"{name_hint}{ext}"
        dest = VEHICLES_DIR / dest_name
        if dest.exists():
            dest_name = f"{name_hint}_{int(time.time())}{ext}"
            dest = VEHICLES_DIR / dest_name

        try:
            shutil.copy2(src, dest)
        except Exception as e:
            messagebox.showerror("Photo", f"Impossible de copier la photo:\n{e}")
            return

        self._vehicle_selected_photo_filename = dest_name
        self._update_vehicle_photo_labels_and_preview(dest_name)

    def _on_vehicle_add(self):
        if count_vehicles() >= MAX_VEHICLES:
            messagebox.showwarning("Véhicules", f"Limite atteinte ({MAX_VEHICLES}). Supprime un véhicule pour en ajouter un nouveau.")
            return
        self._clear_vehicle_form()

    def _on_vehicle_save(self):
        nom = (self.vehicle_form["nom"].get() or "").strip()
        if not nom:
            messagebox.showerror("Véhicule", "Le champ 'Nom' est obligatoire.")
            return

        marque = (self.vehicle_form["marque"].get() or "").strip()
        modele = (self.vehicle_form["modele"].get() or "").strip()
        motorisation = (self.vehicle_form["motorisation"].get() or "").strip()
        energie = (self.vehicle_form["energie"].get() or "").strip()
        immat = (self.vehicle_form["immat"].get() or "").strip()
        photo = self._vehicle_selected_photo_filename

        annee_txt = (self.vehicle_form["annee"].get() or "").strip()
        annee = None
        if annee_txt:
            try:
                annee = int(annee_txt)
                if not (1900 <= annee <= 2100):
                    raise ValueError
            except Exception:
                messagebox.showerror("Véhicule", "Année invalide (ex: 2012).")
                return

        try:
            if self._vehicle_selected_id is None:
                if count_vehicles() >= MAX_VEHICLES:
                    messagebox.showwarning("Véhicules", f"Limite atteinte ({MAX_VEHICLES}).")
                    return
                new_id = add_vehicle(nom, marque, modele, motorisation, energie, annee, immat, photo)
                self._vehicle_selected_id = new_id
                if self.vehicle_id_active is None:
                    self.vehicle_id_active = new_id
                    set_config("active_vehicle_id", str(new_id))
            else:
                update_vehicle(self._vehicle_selected_id, nom, marque, modele, motorisation, energie, annee, immat, photo)

        except sqlite3.IntegrityError:
            messagebox.showerror("Véhicule", "Ce nom existe déjà. Choisis un pseudo différent.")
            return
        except Exception as e:
            messagebox.showerror("Véhicule", str(e))
            return

        self._refresh_all_vehicles_ui()
        self._update_vehicle_photo_labels_and_preview(photo)
        if self.vehicle_id_active == self._vehicle_selected_id:
            self._refresh_vehicle_photo_and_info()
            self._refresh_stats()

    def _on_vehicle_delete(self):
        if self._vehicle_selected_id is None:
            messagebox.showwarning("Véhicule", "Sélectionne un véhicule à supprimer.")
            return
        v = get_vehicle(self._vehicle_selected_id)
        if not v:
            return
        nom = v[1]
        if not messagebox.askyesno("Confirmation", f"Supprimer le véhicule '{nom}' ?"):
            return
        try:
            delete_vehicle(self._vehicle_selected_id)
        except Exception as e:
            messagebox.showerror("Suppression", str(e))
            return

        if self.vehicle_id_active == self._vehicle_selected_id:
            self.vehicle_id_active = None
            set_config("active_vehicle_id", "")

        self._clear_vehicle_form()
        self._refresh_all_vehicles_ui()
        self._restore_active_vehicle()

    def _on_vehicle_set_active(self):
        if self._vehicle_selected_id is None:
            messagebox.showwarning("Véhicule", "Sélectionne un véhicule à définir actif.")
            return
        self._set_active_vehicle(self._vehicle_selected_id)
        self.notebook.select(self.tab_pleins)


if __name__ == "__main__":
    app = GarageApp()
    app.mainloop()