#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Garage — v4.5.30 (clean, single-file)

Données utilisateur :
- Base de données : garage.db dans le dossier utilisateur
- Photos véhicules : dossier utilisateur (vehicle_photos)
- Aide : AIDE.md embarqué dans les ressources de l'application

Conventions d’emplacement :
- macOS : ~/Library/Application Support/Garage
- Linux : ~/.local/share/Garage (XDG)
- Windows : %APPDATA%\\Garage

Fonctions :
- Flotte de véhicules (CRUD + photos utilisateur)
- Pleins (CRUD + autocomplétion Lieu)
- Entretiens (types + CRUD)
- Onglet Général : 2 véhicules par page, conso moyenne, état batterie,
  coût estimé, rappels filtrés (uniquement cochés)
- Onglet graphiques (3 graphes)

Compat :
- Tkinter standard
- SQLite
- Python 3.10+ (OK 3.13)
"""

from __future__ import annotations


# --- Initialisation base de données (modèle -> garage.db) ---
import os
import shutil
import sqlite3
import sys

from app_paths import (
    ASSETS_DIR,
    BASE_DIR,
    DB_FILE,
    USER_DIR,
    VEHICLE_PHOTOS_DIR,
    resource_path,
)
from database import (
    _connect_db,
    _ensure_schema,
    ensure_database,
)
from date_utils import _parse_iso_date
from fuel_repository import (
    delete_plein,
    get_plein,
    insert_plein,
    list_pleins,
    list_pleins_lieux,
    update_plein,
)
from graph_repository import (
    list_fill_consumption_points,
    list_fuel_price_points,
    list_maintenance_cost_by_month,
    list_maintenance_cost_points,
)
from maintenance_repository import (
    delete_entretien,
    get_entretien,
    get_last_battery_voltage,
    insert_entretien,
    list_entretiens_full,
    update_entretien,
)
from maintenance_service import compute_reminder_status, estimate_maintenance_cost_next_months, last_km_any
from maintenance_type_repository import (
    create_type_for_vehicle,
    delete_type_from_vehicle,
    list_vehicle_types,
    set_vehicle_type_enabled,
    update_type,
)
from preconisation_repository import (
    delete_preconisation,
    insert_preconisation,
    list_preconisations,
    update_preconisation,
)
from statistics_service import conso_moy_l100
from vehicle_repository import (
    delete_vehicle,
    get_vehicle,
    insert_vehicle,
    list_vehicles,
    update_vehicle,
)
from vehicle_photo_cleanup import cleanup_orphan_vehicle_photos
from value_utils import _safe_float, _safe_int

os.makedirs(USER_DIR, exist_ok=True)


# Assure la base de données au démarrage.
ensure_database()
# --- AIDE (style) ---
HELP_FONT_FAMILY = "TkDefaultFont"  # Police de TK pour eviter le ghost des emojis ésseulés
HELP_FONT_SIZE = 20                 # Taille de la police de l'aide
HELP_TEXT_COLOR = "#F2F2F2"       # Couleur du texte de l'aide
HELP_BG = "#2B2B2B"               # Fond de l'aide (gris très sombre)
HELP_LOGO_MAX_SIZE = 220            # Taille maximale du logo (px)

#tag special pour laisser passer les emojis ésseulés

if sys.platform == "darwin":
    HELP_EMOJI_FONT_FAMILY = "Apple Color Emoji"
elif sys.platform.startswith("win"):
    HELP_EMOJI_FONT_FAMILY = "Segoe UI Emoji"
else:
    HELP_EMOJI_FONT_FAMILY = "Noto Color Emoji"

# Logo dans l'aide (plafond strict, indépendant du layout)
HELP_LOGO_MAX_WIDTH = 180
HELP_LOGO_MAX_HEIGHT = 90

import os
import re
import sqlite3
import shutil
import tempfile
import uuid
import zipfile
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, date
import sys

# Pillow est recommandé pour afficher les PNG de manière fiable sur macOS.
try:
    from PIL import Image, ImageTk  # type: ignore
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


# Matplotlib pour l'onglet Graphiques (optionnel).
MATPLOTLIB_AVAILABLE = False
Figure = None
FigureCanvasTkAgg = None
NavigationToolbar2Tk = None
MATPLOTLIB_ERROR = ""


def _ensure_matplotlib_available() -> bool:
    """Charge Matplotlib/TkAgg à la demande, après l'initialisation Tk."""
    global MATPLOTLIB_AVAILABLE, MATPLOTLIB_ERROR
    global Figure, FigureCanvasTkAgg, NavigationToolbar2Tk

    if MATPLOTLIB_AVAILABLE and Figure is not None and FigureCanvasTkAgg is not None:
        return True

    try:
        mpl_config_dir = os.path.join(USER_DIR, "matplotlib")
        try:
            os.makedirs(mpl_config_dir, exist_ok=True)
        except Exception:
            mpl_config_dir = tempfile.mkdtemp(prefix="garage-matplotlib-")
        os.environ.setdefault("MPLCONFIGDIR", mpl_config_dir)

        import matplotlib
        matplotlib.use("TkAgg", force=True)
        from matplotlib.figure import Figure as MplFigure  # type: ignore
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg as MplFigureCanvasTkAgg  # type: ignore
        from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk  # type: ignore

        Figure = MplFigure
        FigureCanvasTkAgg = MplFigureCanvasTkAgg
        MATPLOTLIB_AVAILABLE = True
        MATPLOTLIB_ERROR = ""
        return True
    except Exception as exc:
        MATPLOTLIB_AVAILABLE = False
        Figure = None
        FigureCanvasTkAgg = None
        NavigationToolbar2Tk = None
        MATPLOTLIB_ERROR = f"{type(exc).__name__}: {exc}"
        return False

def read_text_file_safely(path: str) -> str:
    """Lit un fichier texte en UTF-8, retourne une chaîne vide en cas d'échec."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

APP_TITLE = "Garage v4.5.30"


# ----------------- Helpers -----------------


def _default_backup_filename() -> str:
    return f"Garage-sauvegarde-{date.today().strftime('%Y-%m-%d')}.zip"


def _backup_sqlite_database(src_db: str, dst_db: str) -> None:
    src = sqlite3.connect(src_db)
    dst = sqlite3.connect(dst_db)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def _add_directory_to_zip(zipf: zipfile.ZipFile, src_dir: str, arc_root: str, exclude_paths: set[str] | None = None) -> None:
    exclude_paths = exclude_paths or set()

    def _same_path(path: str) -> bool:
        try:
            real = os.path.normcase(os.path.realpath(path))
        except Exception:
            real = os.path.normcase(os.path.abspath(path))
        return real in exclude_paths

    zipf.writestr(arc_root.rstrip("/").replace("\\", "/") + "/", "")
    for root, dirs, files in os.walk(src_dir):
        rel_root = os.path.relpath(root, src_dir)
        if rel_root == ".":
            rel_root = ""

        dirs[:] = [dirname for dirname in dirs if not _same_path(os.path.join(root, dirname))]

        for dirname in dirs:
            dir_path = os.path.join(root, dirname)
            if _same_path(dir_path):
                continue
            rel_dir = os.path.normpath(os.path.join(rel_root, dirname)) if rel_root else dirname
            arcname = os.path.join(arc_root, rel_dir).replace("\\", "/").rstrip("/") + "/"
            zipf.writestr(arcname, "")

        for filename in files:
            file_path = os.path.join(root, filename)
            if _same_path(file_path):
                continue
            rel_file = os.path.normpath(os.path.join(rel_root, filename)) if rel_root else filename
            arcname = os.path.join(arc_root, rel_file).replace("\\", "/")
            zipf.write(file_path, arcname)


def export_backup(zip_path: str) -> None:
    final_zip_path = os.path.abspath(zip_path)
    final_dir = os.path.dirname(final_zip_path) or os.getcwd()
    os.makedirs(final_dir, exist_ok=True)

    fd, tmp_zip_path = tempfile.mkstemp(prefix=".garage-backup-", suffix=".zip", dir=final_dir)
    os.close(fd)

    try:
        with tempfile.TemporaryDirectory(prefix="garage-backup-") as tmp_dir:
            tmp_db_path = os.path.join(tmp_dir, "garage.db")
            _backup_sqlite_database(DB_FILE, tmp_db_path)

            exclude_paths = {
                os.path.normcase(os.path.realpath(tmp_zip_path)),
                os.path.normcase(os.path.realpath(final_zip_path)),
            }

            with zipfile.ZipFile(tmp_zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(tmp_db_path, "garage.db")
                if os.path.isdir(VEHICLE_PHOTOS_DIR):
                    _add_directory_to_zip(zipf, VEHICLE_PHOTOS_DIR, "vehicle_photos", exclude_paths)

        os.replace(tmp_zip_path, final_zip_path)
    except Exception:
        try:
            if os.path.exists(tmp_zip_path):
                os.remove(tmp_zip_path)
        except Exception:
            pass
        raise


def _pre_import_backup_filename() -> str:
    return f"Garage-sauvegarde-avant-import-{datetime.now().strftime('%Y-%m-%d-%H%M%S')}.zip"


def _is_safe_zip_member(name: str) -> bool:
    if not name or "\x00" in name:
        return False
    if "\\" in name or ":" in name:
        return False
    if name.startswith("/") or name.startswith("\\"):
        return False
    if re.match(r"^[A-Za-z]:", name):
        return False

    stripped = name.rstrip("/")
    if not stripped:
        return False

    parts = stripped.split("/")
    return all(part not in ("", ".", "..") for part in parts)


def _is_zip_symlink(info: zipfile.ZipInfo) -> bool:
    return ((info.external_attr >> 16) & 0o170000) == 0o120000


def _safe_extract_path(base_dir: str, relative_path: str) -> str:
    target = os.path.realpath(os.path.join(base_dir, relative_path))
    base = os.path.realpath(base_dir)
    if os.path.commonpath([base, target]) != base:
        raise ValueError("L'archive contient un chemin dangereux.")
    return target


def _remove_path_if_exists(path: str) -> None:
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def _extract_backup_zip_safely(zip_path: str, extract_dir: str) -> tuple[str, str | None]:
    try:
        with zipfile.ZipFile(zip_path, "r") as zipf:
            bad_member = zipf.testzip()
            if bad_member:
                raise ValueError(f"L'archive ZIP est corrompue (entrée illisible : {bad_member}).")

            db_info = None
            has_vehicle_photos = False
            for info in zipf.infolist():
                if not _is_safe_zip_member(info.filename):
                    raise ValueError(f"L'archive contient un chemin non autorisé : {info.filename}")
                if _is_zip_symlink(info):
                    raise ValueError(f"L'archive contient un lien symbolique non autorisé : {info.filename}")

                member_name = info.filename.rstrip("/")
                if member_name == "garage.db":
                    if info.is_dir():
                        raise ValueError("L'entrée garage.db de l'archive n'est pas un fichier.")
                    db_info = info
                elif member_name == "vehicle_photos":
                    if not info.is_dir():
                        raise ValueError("L'entrée vehicle_photos de l'archive n'est pas un dossier.")
                    has_vehicle_photos = True
                elif member_name.startswith("vehicle_photos/"):
                    has_vehicle_photos = True

            if db_info is None:
                raise ValueError("L'archive ne contient pas de fichier garage.db.")

            db_path = _safe_extract_path(extract_dir, "garage.db")
            with zipf.open(db_info, "r") as src, open(db_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            photos_dir = None
            if has_vehicle_photos:
                photos_dir = _safe_extract_path(extract_dir, "vehicle_photos")
                os.makedirs(photos_dir, exist_ok=True)
                for info in zipf.infolist():
                    member_name = info.filename.rstrip("/")
                    if member_name == "vehicle_photos":
                        continue
                    if not member_name.startswith("vehicle_photos/"):
                        continue

                    rel = member_name[len("vehicle_photos/"):]
                    if not rel:
                        continue
                    target_path = _safe_extract_path(photos_dir, rel)
                    if info.is_dir():
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with zipf.open(info, "r") as src, open(target_path, "wb") as dst:
                            shutil.copyfileobj(src, dst)

            return db_path, photos_dir
    except zipfile.BadZipFile as exc:
        raise ValueError("Le fichier sélectionné n'est pas une archive ZIP valide.") from exc


def _validate_garage_database(db_path: str) -> None:
    required_tables = {
        "vehicules": {"id"},
        "pleins": {"id", "vehicule_id"},
        "entretien_types": {"id", "nom"},
        "vehicule_entretien_types": {"vehicule_id", "type_id"},
        "entretiens": {"id", "vehicule_id"},
    }

    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA integrity_check")
        integrity_rows = cur.fetchall()
        if len(integrity_rows) != 1 or str(integrity_rows[0][0]).lower() != "ok":
            raise ValueError("Le contrôle d'intégrité SQLite a échoué.")

        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row["name"] for row in cur.fetchall()}
        missing_tables = sorted(set(required_tables) - existing_tables)
        if missing_tables:
            raise ValueError("La base SQLite ne ressemble pas à une base Garage.")

        for table, required_columns in required_tables.items():
            cur.execute(f"PRAGMA table_info({table})")
            existing_columns = {row["name"] for row in cur.fetchall()}
            if not required_columns.issubset(existing_columns):
                raise ValueError("La base SQLite ne contient pas la structure attendue pour Garage.")
    except sqlite3.DatabaseError as exc:
        raise ValueError("Le fichier garage.db de l'archive n'est pas une base SQLite valide.") from exc
    finally:
        try:
            if conn is not None:
                conn.close()
        except Exception:
            pass


def import_backup(zip_path: str) -> str:
    with tempfile.TemporaryDirectory(prefix="garage-import-verify-") as verify_dir:
        imported_db, imported_photos = _extract_backup_zip_safely(zip_path, verify_dir)
        _validate_garage_database(imported_db)

        backups_dir = os.path.join(USER_DIR, "backups")
        os.makedirs(backups_dir, exist_ok=True)
        safety_backup_path = os.path.join(backups_dir, _pre_import_backup_filename())
        export_backup(safety_backup_path)

        operation_dir = tempfile.mkdtemp(prefix=".garage-import-", dir=USER_DIR)
        rollback_dir = os.path.join(operation_dir, "rollback")
        staging_dir = os.path.join(operation_dir, "staging")
        os.makedirs(rollback_dir, exist_ok=True)
        os.makedirs(staging_dir, exist_ok=True)

        staged_db = os.path.join(staging_dir, "garage.db")
        staged_photos = os.path.join(staging_dir, "vehicle_photos")
        shutil.copy2(imported_db, staged_db)
        if imported_photos and os.path.isdir(imported_photos):
            shutil.copytree(imported_photos, staged_photos)

        rollback_db = os.path.join(rollback_dir, "garage.db")
        rollback_photos = os.path.join(rollback_dir, "vehicle_photos")
        db_moved = False
        photos_moved = False
        db_installed = False
        photos_installed = False
        cleanup_operation_dir = False

        try:
            if os.path.exists(DB_FILE):
                os.replace(DB_FILE, rollback_db)
                db_moved = True
            if os.path.exists(VEHICLE_PHOTOS_DIR):
                os.replace(VEHICLE_PHOTOS_DIR, rollback_photos)
                photos_moved = True

            os.replace(staged_db, DB_FILE)
            db_installed = True
            if os.path.isdir(staged_photos):
                os.replace(staged_photos, VEHICLE_PHOTOS_DIR)
                photos_installed = True

            cleanup_operation_dir = True
            return safety_backup_path
        except Exception as exc:
            rollback_errors = []
            try:
                if db_moved and os.path.exists(rollback_db):
                    _remove_path_if_exists(DB_FILE)
                    os.replace(rollback_db, DB_FILE)
                elif db_installed:
                    _remove_path_if_exists(DB_FILE)
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))
            try:
                if photos_moved and os.path.exists(rollback_photos):
                    _remove_path_if_exists(VEHICLE_PHOTOS_DIR)
                    os.replace(rollback_photos, VEHICLE_PHOTOS_DIR)
                elif photos_installed:
                    _remove_path_if_exists(VEHICLE_PHOTOS_DIR)
            except Exception as rollback_exc:
                rollback_errors.append(str(rollback_exc))

            if rollback_errors:
                raise RuntimeError(
                    "L'importation a échoué et la restauration automatique n'a pas pu être finalisée.\n"
                    f"Dossier temporaire conservé : {operation_dir}\n"
                    f"Détail : {exc}"
                ) from exc
            cleanup_operation_dir = True
            raise RuntimeError(
                "L'importation a échoué. Vos données précédentes ont été restaurées automatiquement.\n"
                f"Détail : {exc}"
            ) from exc
        finally:
            if cleanup_operation_dir:
                try:
                    shutil.rmtree(operation_dir)
                except Exception:
                    pass


def _ensure_assets_dir():
    os.makedirs(ASSETS_DIR, exist_ok=True)

def _ensure_vehicle_photos_dir():
    os.makedirs(VEHICLE_PHOTOS_DIR, exist_ok=True)



def _copy_vehicle_photo(src_path: str, vehicle_id: int | None = None) -> str | None:
    """Copie une image (PNG/JPG/JPEG/BMP) dans le dossier utilisateur et retourne le nom PNG stocké en DB.

    Pour fiabiliser l'affichage Tkinter et le packaging, l'image est toujours convertie en PNG.
    """
    if not src_path:
        return None
    _ensure_vehicle_photos_dir()

    base = os.path.basename(src_path)
    name, ext = os.path.splitext(base)
    ext_l = ext.lower()

    allowed = {".png", ".jpg", ".jpeg", ".bmp"}
    if ext_l not in allowed:
        raise ValueError("Format non supporté. Veuillez choisir une image PNG, JPG/JPEG ou BMP.")

    # Nom stable : V<ID>.png (l'ID vient de SQLite, donc ne bouge pas)
    out_name = f"V{int(vehicle_id)}.png" if vehicle_id else f"Vtmp_{uuid.uuid4().hex[:8]}.png"
    dst = os.path.join(VEHICLE_PHOTOS_DIR, out_name)

    try:
        # Pillow est déjà utilisé dans l'application (Image/ImageTk).
        from PIL import Image, ImageOps  # type: ignore
        img = Image.open(src_path)
        # Corrige l'orientation EXIF (souvent utile pour les JPG)
        try:
            img = ImageOps.exif_transpose(img)
        except Exception:
            pass
        img = img.convert("RGBA")
        img.save(dst, format="PNG", optimize=True)
    except Exception:
        # Fallback minimal : si ce n'est pas un PNG, Tkinter ne pourra pas le lire.
        if ext_l != ".png":
            raise ValueError("Impossible de convertir l'image. Veuillez installer Pillow ou utiliser un PNG.")
        shutil.copy2(src_path, dst)

    return out_name



def _load_vehicle_photo_tk(photo_file: str | None, max_w=360, max_h=220):
    """Charge un PNG via PhotoImage et le réduit (subsample) pour l'affichage."""
    if not photo_file:
        return None
    name = os.path.basename(str(photo_file).replace("\\", "/"))
    # 1) dossier utilisateur (recommandé)
    path = os.path.join(VEHICLE_PHOTOS_DIR, name)
    # 2) compat ancien : ./assets
    if not os.path.exists(path):
        path = os.path.join(ASSETS_DIR, name)
    if not os.path.exists(path):
        return None
    try:
        img = tk.PhotoImage(file=path)
    except Exception:
        return None

    import math


    try:
        w, h = img.width(), img.height()
        sx = max(1, math.ceil(w / max_w))
        sy = max(1, math.ceil(h / max_h))
        s = max(sx, sy)
        if s > 1:
            img = img.subsample(s, s)
    except Exception:
        pass
    return img


def _fmt_date(d) -> str:
    dd = _parse_iso_date(d)
    return dd.strftime("%d/%m/%Y") if dd else ""


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

        self._theme_name = "Midnight Garage"

        self._apply_platform_theme() 

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
        self.geometry("1280x680")
        self.minsize(1100, 620)

        if not os.path.exists(DB_FILE):
            messagebox.showerror("DB introuvable", f"Impossible de trouver :\n{DB_FILE}\n\nLa base est créée automatiquement dans le dossier de données utilisateur.")
            raise SystemExit(1)

        _ensure_schema()
        cleanup_orphan_vehicle_photos()
        _ensure_assets_dir()

        self.vehicles_rows = list_vehicles()
        if not self.vehicles_rows:
            messagebox.showinfo("Aucun véhicule", "La base est vide. Ajoutez votre premier véhicule")
            self.active_vehicle_id = None
        else:
            self.active_vehicle_id = int(self.vehicles_rows[0]["id"])

        self._general_card_imgs = {}
        self._veh_photo_img = None
        self._veh_mode = "view"  # view/add/edit
        self._veh_photo_src_path = None
        self._pleins_lieux_all = []
        self._type_name_to_id = {}
        self.selected_type_id = None

        self.status = tk.StringVar(value="")

        self._build_ui()
        self._refresh_all()

    def _apply_platform_theme(self) -> None:
        import sys
        from tkinter import ttk

        is_mac = sys.platform == "darwin"
        is_linux = sys.platform.startswith("linux")
        is_windows = sys.platform.startswith("win")

               # bibli de themes pour le selecteur
        THEMES = {
            # ===== Thèmes sombres (sobres / quotidiens) =====
            "[Sombre] Midnight Garage": dict(
                BG="#151515", PANEL="#1F1F1F", FIELD="#2A2A2A",
                FG="#EAEAEA", FIELD_FG="#F0F0F0", ACCENT="#FF9800"
            ),
            "[Sombre] AIR-KLM Night flight": dict(
                BG="#0B1E2D", PANEL="#102A3D", FIELD="#16384F",
                FG="#EAF6FF", FIELD_FG="#FFFFFF", ACCENT="#00A1DE"
            ),
            "[Sombre] Café Serré": dict(
                BG="#1B120C", PANEL="#2A1C14", FIELD="#3A281D",
                FG="#F2E6D8", FIELD_FG="#FFF4E6", ACCENT="#C28E5C"
            ),
            "[Sombre] Matrix Déjà Vu": dict(
                BG="#000A00", PANEL="#001F00", FIELD="#003300",
                FG="#00FF66", FIELD_FG="#66FF99", ACCENT="#00FF00"
            ),
            "[Sombre] Miami Vice 1987": dict(
                BG="#14002E", PANEL="#2B0057", FIELD="#004D4D",
                FG="#FFF0FF", FIELD_FG="#FFFFFF", ACCENT="#00FFD5"
            ),
            "[Sombre] Cyber Licorne": dict(
                BG="#1A0026", PANEL="#2E004F", FIELD="#3D0066",
                FG="#F6E7FF", FIELD_FG="#FFFFFF", ACCENT="#FF2CF7"
            ),
            # ===== Thèmes clairs =====
            "[Clair] AIR-KLM Day flight": dict(
                BG="#EAF6FF", PANEL="#D6EEF9", FIELD="#FFFFFF",
                FG="#0B2A3F", FIELD_FG="#0B2A3F", ACCENT="#00A1DE"
            ),
            "[Clair] Matin Brumeux": dict(
                BG="#E6E7E8", PANEL="#D4D7DB", FIELD="#FFFFFF",
                FG="#1E1F22", FIELD_FG="#1E1F22", ACCENT="#6B7C93"
            ),
            "[Clair] Latte Vanille": dict(
                BG="#FAF6F1", PANEL="#EFE6DC", FIELD="#FFFFFF",
                FG="#3D2E22", FIELD_FG="#3D2E22", ACCENT="#D8B892"
            ),
            "[Clair] Miellerie La Divette": dict(
                BG="#E6B65C", PANEL="#F5E6CC", FIELD="#FFFFFF",
                FG="#50371A", FIELD_FG="#50371A", ACCENT="#F2B705"
            ),
            # ===== Thèmes Pouêt-Pouêt (mais distincts) =====
             "[Pouêt] Chewing-gum Océan": dict(
                BG="#00A6C8", PANEL="#0083A1", FIELD="#00C7B7",
                FG="#082026", FIELD_FG="#082026", ACCENT="#FF4FD8"
            ),
            "[Pouêt] Pamplemousse": dict(
                BG="#FF4A1C", PANEL="#E63B10", FIELD="#FF7A00",
                FG="#1A0B00", FIELD_FG="#1A0B00", ACCENT="#00E5FF"
            ),
            "[Pouêt] Raisin Toxique": dict(
                BG="#7A00FF", PANEL="#5B00C9", FIELD="#B000FF",
                FG="#0F001A", FIELD_FG="#0F001A", ACCENT="#39FF14"
            ),
            "[Pouêt] Citron qui pique": dict(
                BG="#FFF200", PANEL="#E6D800", FIELD="#FFF7A6",
                FG="#1A1A00", FIELD_FG="#1A1A00", ACCENT="#0066FF"
            ),  
            "[Pouêt] Barbie Apocalypse": dict(
                BG="#FF1493", PANEL="#004D40", FIELD="#1B5E20",
                FG="#E8FFF8", FIELD_FG="#FFFFFF", ACCENT="#FFEB3B" 
            ),   
            "[Pouêt] Compagnie Créole": dict(
                BG="#8B3A1A", PANEL="#F2C94C", FIELD="#FFFFFF",
                FG="#5A2E0C", FIELD_FG="#5A2E0C", ACCENT="#8B3A1A"
            ),    
       }
        self._themes = THEMES
        self._theme_names = list(THEMES.keys())

        theme_name = getattr(self, "_theme_name", "Midnight Garage")
        default_theme = next(iter(THEMES.values()))
        t = THEMES.get(theme_name, default_theme)


        BG = t["BG"]
        PANEL = t["PANEL"]
        FIELD = t["FIELD"]
        FG = t["FG"]
        FIELD_FG = t["FIELD_FG"]
        ACCENT = t["ACCENT"]

        # Texte dans les champs (par défaut = FG si non défini)
        FIELD_FG = locals().get("FIELD_FG", FG)

        # --- Tk (classique) ---
        # Affecte au root + palette par défaut pour tk widgets
        self.configure(bg=BG)
        try:
            self.option_add("*Background", BG)
            self.option_add("*Foreground", FG)
            self.option_add("*insertBackground", FG)
            self.option_add("*selectBackground", ACCENT)
            self.option_add("*selectForeground", FG)
        except Exception:
            pass

        # --- ttk (thèmes/widgets ttk) ---
        style = ttk.Style(self)


        # macOS (aqua) et Windows : thèmes natifs parfois “bloquants” -> forcer un thème modifiable
        if is_windows or is_mac:
            for candidate in ("clam", "alt", "default"):
                try:
                    style.theme_use(candidate)
                    break
                except Exception:
                    pass

        # Dropdown Combobox (la liste) : c'est un Listbox Tk -> toutes plateformes
        self.option_add("*TCombobox*Listbox.background", FIELD)
        self.option_add("*TCombobox*Listbox.foreground", FIELD_FG)
        self.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", FIELD_FG)
        self.option_add("*TCombobox*Listbox.font", "TkDefaultFont")
        self.option_add("*TCombobox*Listbox.width", 60)

        # Sur Linux, garder le thème système (Adwaita) mais surcharger les couleurs
        # (sur macOS idem, ça évite de casser l'apparence native)
        style.configure(".", background=BG, foreground=FG)

        # Frames / Panes / Notebook
        style.configure("TFrame", background=BG)
        style.configure("TLabelframe", background=BG)
        style.configure("TLabelframe.Label", background=BG, foreground=FG)

        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=FG)
        style.map("TNotebook.Tab",
                background=[("selected", BG)],
                foreground=[("selected", FG)])

        # Labels, Buttons
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", padding=6)

        
        # Entrées
        style.configure("TEntry", fieldbackground=FIELD, foreground=FIELD_FG)

        # Combobox (champ fermé)
        style.configure(
            "TCombobox",
            fieldbackground=FIELD,
            background=PANEL,
            foreground=FIELD_FG,
            arrowcolor=FIELD_FG,
        )

        # Combobox (liste déroulante + sélection)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD)],
            background=[("readonly", PANEL)],
            foreground=[("readonly", FIELD_FG)],
            selectbackground=[("readonly", ACCENT)],
            selectforeground=[("readonly", FIELD_FG)],
        )

        # --- IMPORTANT : états readonly/disabled (sinon gris illisible sur thème sombre) ---
        style.map(
            "TEntry",
            fieldbackground=[("readonly", FIELD), ("disabled", FIELD)],
            foreground=[("readonly", FIELD_FG), ("disabled", FIELD_FG)],
            insertcolor=[("readonly", FIELD_FG), ("disabled", FIELD_FG)],
        )

        style.map(
            "TCombobox",
            fieldbackground=[("readonly", FIELD), ("disabled", FIELD)],
            foreground=[("readonly", FIELD_FG), ("disabled", FIELD_FG)],
            selectbackground=[("readonly", ACCENT)],
            selectforeground=[("readonly", FIELD_FG)],
        )

        # (optionnel) la zone de liste dropdown de la combobox (selon thèmes)
        style.configure("TCombobox", selectbackground=ACCENT, selectforeground=FIELD_FG)



        # Treeview (listes / tableaux)
        style.configure("Treeview", background=FIELD, fieldbackground=FIELD, foreground=FIELD_FG)
        style.configure("Treeview.Heading", background=PANEL, foreground=FG)

        # Garde les valeurs pour un usage ponctuel
        self._ui_colors = {"BG": BG, "FG": FG, "PANEL": PANEL, "FIELD": FIELD, "FIELD_FG": FIELD_FG, "ACCENT": ACCENT}
        

    # ---------- UI Shell ----------
    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.main_shell = ttk.Frame(self)
        self.main_shell.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        self.main_shell.columnconfigure(0, weight=1)
        self.main_shell.rowconfigure(1, weight=1)

        self.main_nav_bar = ttk.Frame(self.main_shell)
        self.main_nav_bar.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.main_nav_bar.columnconfigure(4, weight=1)

        self.btn_nav_general = ttk.Button(self.main_nav_bar, text="Général", command=self._show_general)
        self.btn_nav_pleins = ttk.Button(self.main_nav_bar, text="Pleins", command=self._show_pleins)
        self.btn_nav_ent = ttk.Button(self.main_nav_bar, text="Entretiens", command=self._show_entretiens)
        self.btn_nav_graphs = ttk.Button(self.main_nav_bar, text="Graphiques", command=self._show_graphs)
        self.btn_nav_settings = ttk.Button(self.main_nav_bar, text="Paramètres", command=self._show_settings)

        self.btn_nav_general.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.btn_nav_pleins.grid(row=0, column=1, sticky="w", padx=(0, 6))
        self.btn_nav_ent.grid(row=0, column=2, sticky="w", padx=(0, 6))
        self.btn_nav_graphs.grid(row=0, column=3, sticky="w")
        self.btn_nav_settings.grid(row=0, column=5, sticky="e")

        self.main_page_area = ttk.Frame(self.main_shell)
        self.main_page_area.grid(row=1, column=0, sticky="nsew")
        self.main_page_area.columnconfigure(0, weight=1)
        self.main_page_area.rowconfigure(0, weight=1)

        self.tab_general = ttk.Frame(self.main_page_area, padding=10)
        self.tab_pleins = ttk.Frame(self.main_page_area, padding=10)
        self.tab_ent = ttk.Frame(self.main_page_area, padding=10)
        self.tab_graphs = ttk.Frame(self.main_page_area, padding=10)
        self.tab_settings = ttk.Frame(self.main_page_area, padding=10)

        for page in (
            self.tab_general,
            self.tab_pleins,
            self.tab_ent,
            self.tab_graphs,
            self.tab_settings,
        ):
            page.grid(row=0, column=0, sticky="nsew")

        self._build_general_tab()
        self._build_pleins_tab()
        self._build_entretiens_tab()
        self._build_graphs_tab()
        self._build_settings_tab()
        self.tab_general.tkraise()

    def _show_general(self):
        self.tab_general.tkraise()

    def _show_pleins(self):
        self.tab_pleins.tkraise()

    def _show_entretiens(self):
        self.tab_ent.tkraise()

    def _show_graphs(self):
        self.tab_graphs.tkraise()

    def _show_settings(self):
        self.tab_settings.tkraise()

    def _build_settings_tab(self):
        self.tab_settings.columnconfigure(0, weight=1)
        self.tab_settings.rowconfigure(0, weight=1)

        self.settings_nb = ttk.Notebook(self.tab_settings)
        self.settings_nb.grid(row=0, column=0, sticky="nsew")

        self.settings_vehicles_tab = ttk.Frame(self.settings_nb, padding=10)
        self.settings_maintenance_tab = ttk.Frame(self.settings_nb, padding=10)
        self.settings_preconisations_tab = ttk.Frame(self.settings_nb, padding=10)
        self.settings_appearance_tab = ttk.Frame(self.settings_nb, padding=10)
        self.settings_data_tab = ttk.Frame(self.settings_nb, padding=10)
        self.settings_help_tab = ttk.Frame(self.settings_nb, padding=10)

        self.settings_nb.add(self.settings_vehicles_tab, text="Véhicules")
        self.settings_nb.add(self.settings_maintenance_tab, text="Entretien")
        self.settings_nb.add(self.settings_preconisations_tab, text="Préconisations")
        self.settings_nb.add(self.settings_appearance_tab, text="Apparence")
        self.settings_nb.add(self.settings_data_tab, text="Données")
        self.settings_nb.add(self.settings_help_tab, text="Aide")

        for tab in (
            self.settings_vehicles_tab,
            self.settings_maintenance_tab,
            self.settings_preconisations_tab,
            self.settings_appearance_tab,
            self.settings_data_tab,
            self.settings_help_tab,
        ):
            tab.columnconfigure(0, weight=1)
            tab.rowconfigure(0, weight=1)

        self._build_settings_vehicles()
        self._build_settings_appearance()
        self._build_settings_data()
        self._build_settings_maintenance()
        self._build_settings_preconisations()
        self._build_settings_help()

    def _build_settings_vehicles(self):
        self.settings_vehicles_tab.columnconfigure(0, weight=1)
        self.settings_vehicles_tab.rowconfigure(0, weight=0)
        self.settings_vehicles_tab.rowconfigure(1, weight=0)
        self.settings_vehicles_tab.rowconfigure(2, weight=1)

        top = ttk.Frame(self.settings_vehicles_tab)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Véhicule :").grid(row=0, column=0, sticky="w")
        self.veh_vehicle_var = tk.StringVar(value="")
        self.veh_vehicle_cb = ttk.Combobox(top, textvariable=self.veh_vehicle_var, state="readonly")
        self.veh_vehicle_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.veh_vehicle_cb.bind("<<ComboboxSelected>>", self._on_veh_vehicle_change)

        btns = ttk.Frame(self.settings_vehicles_tab)
        btns.grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Button(btns, text="Ajouter", command=self._veh_add_mode).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(btns, text="Modifier", command=self._veh_edit_mode).grid(row=0, column=1, padx=(0, 8))
        ttk.Button(btns, text="Supprimer", command=self._veh_delete).grid(row=0, column=2)
        self.veh_btn_save_top = ttk.Button(btns, text="Enregistrer", command=self._veh_save)
        self.veh_btn_save_top.grid(row=0, column=3, padx=(8, 0))

        body = ttk.Frame(self.settings_vehicles_tab)
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

        self.veh_vars = {
            "nom": tk.StringVar(value=""),
            "marque": tk.StringVar(value=""),
            "modele": tk.StringVar(value=""),
            "motorisation": tk.StringVar(value=""),
            "energie": tk.StringVar(value=""),
            "annee": tk.StringVar(value=""),
            "immatriculation": tk.StringVar(value=""),
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
        ]
        for i, (lab, key) in enumerate(fields):
            ttk.Label(form, text=lab + " :").grid(row=i, column=0, sticky="e", padx=(0, 10), pady=4)
            e = ttk.Entry(form, textvariable=self.veh_vars[key], width=38)
            e.grid(row=i, column=1, sticky="w", pady=4)
            self.veh_entries[key] = e

        self._veh_set_mode("view")

    def _build_settings_appearance(self):
        box = ttk.Frame(self.settings_appearance_tab)
        box.grid(row=0, column=0, sticky="nw")

        ttk.Label(box, text="Thème :").grid(row=0, column=0, sticky="w")

        theme_values = getattr(self, "_theme_names", ["Midnight Garage"])
        current = getattr(self, "_theme_name", theme_values[0])

        self.theme_var = tk.StringVar(value=current)
        self.theme_cb = ttk.Combobox(
            box,
            textvariable=self.theme_var,
            values=theme_values,
            state="readonly",
            width=27,
        )
        self.theme_cb.grid(row=0, column=1, padx=(8, 0), sticky="w")
        self._set_combobox_dropdown_width(self.theme_cb, 60)

        self.theme_cb.bind("<<ComboboxSelected>>", self._on_theme_change)

    def _build_settings_data(self):
        box = ttk.Frame(self.settings_data_tab)
        box.grid(row=0, column=0, sticky="nw")

        self.btn_export_backup = ttk.Button(
            box,
            text="Exporter une sauvegarde",
            command=self._export_backup_dialog,
        )
        self.btn_export_backup.grid(row=0, column=0)

        self.btn_import_backup = ttk.Button(
            box,
            text="Importer une sauvegarde",
            command=self._import_backup_dialog,
        )
        self.btn_import_backup.grid(row=0, column=1, padx=(10, 0))

    def _build_settings_maintenance(self):
        self.settings_maintenance_tab.columnconfigure(0, weight=1)
        self.settings_maintenance_tab.rowconfigure(0, weight=0)
        self.settings_maintenance_tab.rowconfigure(1, weight=1)

        top = ttk.Frame(self.settings_maintenance_tab)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Véhicule :").grid(row=0, column=0, sticky="w")
        self.settings_maintenance_vehicle_var = tk.StringVar(value="")
        self.settings_maintenance_vehicle_cb = ttk.Combobox(
            top,
            textvariable=self.settings_maintenance_vehicle_var,
            state="readonly",
        )
        self.settings_maintenance_vehicle_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.settings_maintenance_vehicle_cb.bind("<<ComboboxSelected>>", self._on_settings_maintenance_vehicle_change)

        box_type = ttk.Labelframe(self.settings_maintenance_tab, text="Type d'entretien (pour ce véhicule)", padding=10)
        box_type.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
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
        box_type.rowconfigure(2, weight=1)
        box_list.rowconfigure(0, weight=1)

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
        self.tree_types.configure(yscrollcommand=ysb_t.set)

    def _build_settings_preconisations(self):
        self.settings_preconisations_tab.columnconfigure(0, weight=1)
        self.settings_preconisations_tab.rowconfigure(0, weight=0)
        self.settings_preconisations_tab.rowconfigure(1, weight=1)

        top = ttk.Frame(self.settings_preconisations_tab)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Véhicule :").grid(row=0, column=0, sticky="w")
        self.settings_preco_vehicle_var = tk.StringVar(value="")
        self.settings_preco_vehicle_cb = ttk.Combobox(
            top,
            textvariable=self.settings_preco_vehicle_var,
            state="readonly",
        )
        self.settings_preco_vehicle_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.settings_preco_vehicle_cb.bind("<<ComboboxSelected>>", self._on_settings_preco_vehicle_change)

        preco_box = ttk.Labelframe(self.settings_preconisations_tab, text="Préconisations constructeur", padding=10)
        preco_box.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        preco_box.columnconfigure(0, weight=1)
        preco_box.rowconfigure(1, weight=1)

        add_line = ttk.Frame(preco_box)
        add_line.grid(row=0, column=0, sticky="ew")
        add_line.columnconfigure(1, weight=1)

        ttk.Button(add_line, text="+", width=3, command=self._preco_add).grid(row=0, column=0, sticky="w")
        self.preco_entry_var = tk.StringVar(value="")
        ttk.Entry(add_line, textvariable=self.preco_entry_var).grid(row=0, column=1, sticky="ew", padx=(8, 0))

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

    def _build_settings_help(self):
        self.settings_help_tab.columnconfigure(0, weight=1)
        self.settings_help_tab.rowconfigure(0, weight=0)
        self.settings_help_tab.rowconfigure(1, weight=1)

        self.help_logo_label = ttk.Label(self.settings_help_tab, text="")
        self.help_logo_label.grid(row=0, column=0, sticky="n", pady=(0, 10))

        help_text_frame = ttk.Frame(self.settings_help_tab)
        help_text_frame.grid(row=1, column=0, sticky="nsew")
        help_text_frame.columnconfigure(0, weight=1)
        help_text_frame.rowconfigure(0, weight=1)

        help_scroll = ttk.Scrollbar(help_text_frame, orient="vertical")
        help_scroll.grid(row=0, column=1, sticky="ns")

        self.help_text = tk.Text(
            help_text_frame,
            width=1,
            height=1,
            wrap="word",
            bg=HELP_BG,
            fg=HELP_TEXT_COLOR,
            bd=0,
            highlightthickness=0,
            font=(HELP_FONT_FAMILY, HELP_FONT_SIZE),
            yscrollcommand=help_scroll.set,
        )
        self.help_text.grid(row=0, column=0, sticky="nsew")
        help_scroll.config(command=self.help_text.yview)

        self._load_logo_image()
        self._load_help_into_widget()

    def _set_status(self, txt: str):
        self.status.set(txt)

    def _export_backup_dialog(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Exporter une sauvegarde",
            defaultextension=".zip",
            initialfile=_default_backup_filename(),
            filetypes=[
                ("Archives ZIP", "*.zip"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not path:
            return

        try:
            export_backup(path)
        except Exception as exc:
            messagebox.showerror(
                "Export impossible",
                "La sauvegarde n'a pas pu être créée.\n\n"
                f"Détail : {exc}",
            )
            return

        messagebox.showinfo(
            "Sauvegarde créée",
            "Sauvegarde créée avec succès.\n"
            "La base de données et les photos des véhicules ont été exportées.",
        )
        self._set_status("Sauvegarde exportée.")

    def _import_backup_dialog(self) -> None:
        path = filedialog.askopenfilename(
            title="Importer une sauvegarde",
            filetypes=[
                ("Archives ZIP", "*.zip"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not path:
            return

        try:
            with tempfile.TemporaryDirectory(prefix="garage-import-check-") as check_dir:
                imported_db, _imported_photos = _extract_backup_zip_safely(path, check_dir)
                _validate_garage_database(imported_db)
        except Exception as exc:
            messagebox.showerror(
                "Import impossible",
                "La sauvegarde sélectionnée n'est pas valide.\n\n"
                f"Détail : {exc}",
            )
            return

        confirmed = messagebox.askyesno(
            "Importer une sauvegarde",
            "Cette opération remplacera les données actuellement utilisées par Garage\n"
            "par celles contenues dans la sauvegarde sélectionnée.\n\n"
            "Les véhicules, pleins, entretiens et photos actuels seront remplacés.\n\n"
            "Une sauvegarde de sécurité de vos données actuelles sera créée automatiquement\n"
            "avant l'importation.\n\n"
            "Voulez-vous vraiment continuer ?",
            icon="warning",
            default=messagebox.NO,
        )
        if not confirmed:
            return

        try:
            import_backup(path)
        except Exception as exc:
            messagebox.showerror(
                "Import impossible",
                "L'importation n'a pas pu être effectuée.\n\n"
                f"Détail : {exc}",
            )
            return

        messagebox.showinfo(
            "Importation terminée",
            "La sauvegarde a été importée avec succès.\n\n"
            "Redémarrez Garage pour utiliser les données restaurées.",
        )
        self._set_status("Sauvegarde importée. Redémarrez Garage.")

    def _read_help_md(self) -> str:
        """Lit AIDE.md (à la racine de l'app) et nettoie le bloc <img> en tête si présent."""
        # AIDE.md est attendu à la racine, au même niveau que garage.py (ou dans le bundle PyInstaller).
        candidates = [
            resource_path("assets/AIDE.md"),
            os.path.join(os.path.abspath(os.path.dirname(__file__)), "AIDE.md"),
            os.path.abspath("assets/AIDE.md"),
        ]
        txt = ""
        for p in candidates:
            if os.path.exists(p):
                txt = read_text_file_safely(p)
                break

        if not txt:
            return (
                "Aide indisponible\n\n"
                "Le fichier AIDE.md n'a pas été trouvé"
            )

        # Si le fichier commence par un bloc HTML (souvent <p align="center"><img ...></p>),
        # on le retire. Certains éditeurs ajoutent ça en tête du Markdown.
        lines = txt.splitlines()

        # On ne traite que si un <img ...> apparaît très tôt dans le fichier
        head = "\n".join(lines[:15]).lower()
        if "<img" in head and "<p" in head:
            i = 0
            # saute les éventuelles lignes vides au début
            while i < len(lines) and lines[i].strip() == "":
                i += 1

            # si on tombe sur un <p ...> on commence à skipper
            if i < len(lines) and lines[i].strip().lower().startswith("<p"):
                i += 1
                # skip jusqu'au </p> inclus (en tolérant multi-lignes)
                while i < len(lines):
                    l = lines[i].strip().lower()
                    if "</p>" in l:
                        i += 1
                        break
                    i += 1

                # retire aussi les lignes vides juste après le bloc
                while i < len(lines) and lines[i].strip() == "":
                    i += 1

                txt = "\n".join(lines[i:]).lstrip()


        return txt

    def _load_help_into_widget(self) -> None:
        """Charge l'aide dans le widget et centre l'affichage."""
        if not hasattr(self, "help_text"):
            return

        content = self._read_help_md()

        self.help_text.config(state="normal")
        self.help_text.delete("1.0", "end")
        
        # bloc qui fait en sorte d'aficher les emojis meme seuls sur une ligne, et en cross OS
        try:
            self.help_text.tag_delete("center")
        except Exception:
            pass
        self.help_text.tag_configure("center", justify="center", foreground=HELP_TEXT_COLOR)

        # --- Tag spécifique pour les lignes emoji-only ---
        try:
            self.help_text.tag_delete("emoji")
        except Exception:
            pass

        try:
            self.help_text.tag_configure(
                "emoji",
                justify="center",
                foreground=HELP_TEXT_COLOR,
                font=(HELP_EMOJI_FONT_FAMILY, HELP_FONT_SIZE),
            )
        except Exception:
            # Si la police emoji n'est pas dispo, on garde au moins centrage + couleur
            self.help_text.tag_configure(
                "emoji",
                justify="center",
                foreground=HELP_TEXT_COLOR,
            )



        self.help_text.mark_set("insert", "1.0")
        for line in content.splitlines():
            stripped = line.strip()

            if stripped == "":
                self.help_text.insert("end", "\n")
                continue

            # Lignes avec lettres/chiffres : centrées via le tag "center"
            if any(ch.isalnum() for ch in stripped):
                self.help_text.insert("end", line + "\n", "center")
            else:
                # Lignes sans alphanum (---, emojis, symboles) : centrées aussi
                # Supprime tabulations et espaces qui créent de grands écarts entre emojis dans Tk
                clean = line.replace("\t", "").replace(" ", "")
                self.help_text.insert("end", clean + "\n", "emoji")



        self.help_text.config(state="disabled")


    def _load_logo_image(self) -> None:
        """Charge le logo PNG (assets/logo.png) et l'affiche en taille raisonnable."""
        if not hasattr(self, "help_logo_label"):
            return

        # Chemins possibles (dev + bundle PyInstaller)
        candidates = [
            # PyInstaller / resource_path
            resource_path(os.path.join("assets", "logo.png")),
            resource_path(os.path.join("assets", "Logo.png")),

            # dev : à côté du fichier
            os.path.join(os.path.abspath(os.path.dirname(__file__)), "assets", "logo.png"),
            os.path.join(os.path.abspath(os.path.dirname(__file__)), "assets", "Logo.png"),

            # dev : depuis cwd
            os.path.abspath(os.path.join("assets", "logo.png")),
            os.path.abspath(os.path.join("assets", "Logo.png")),
        ]
        logo_path = next((p for p in candidates if os.path.exists(p)), "")

        if not logo_path:
            try:
                self.help_logo_label.config(text="Garage", image="")
            except Exception:
                pass
            return

        max_px = int(HELP_LOGO_MAX_SIZE)

        try:
            if PIL_AVAILABLE:
                img = Image.open(logo_path).convert("RGBA")

                # --- HiDPI / Retina : on calcule un facteur d'échelle Tk ---
                try:
                    tk_scale = float(self.tk.call("tk", "scaling"))  # souvent ~2.0 sur Retina
                    
                except Exception:
                    tk_scale = 1.0
                if tk_scale < 1.0:
                    tk_scale = 1.0

                target_px = int(max_px * tk_scale)

                w, h = img.size
                scale = min(target_px / w, target_px / h)
                new_w = max(1, int(w * scale))
                new_h = max(1, int(h * scale))

                img = img.resize((new_w, new_h), Image.LANCZOS)

                self._logo_img = ImageTk.PhotoImage(img)
                self.help_logo_label.config(image=self._logo_img, text="")
                
            else:
                # Fallback Tk : pas de resize natif -> on subsample pour éviter un logo géant
                img = tk.PhotoImage(file=logo_path)

                w, h = img.width(), img.height()
                # facteur entier >=1
                factor = max(1, int(max(w, h) / max_px)) if max(w, h) > max_px else 1
                if factor > 1:
                    img = img.subsample(factor, factor)

                self._logo_img = img
                self.help_logo_label.config(image=self._logo_img, text="")
        except Exception:
            try:
                self.help_logo_label.config(text="Garage", image="")
            except Exception:
                pass

    # forcer la largeur combobox selection thème

    def _set_combobox_dropdown_width(self, cb: ttk.Combobox, chars: int) -> None:
        """Force la largeur (en caractères) de la liste déroulante d'une ttk.Combobox (surtout utile sur Windows)."""
        try:
            popdown = self.tk.call("ttk::combobox::PopdownWindow", cb)
            # Listbox interne : <popdown>.f.l
            self.tk.call(f"{popdown}.f.l", "configure", "-width", int(chars))
        except Exception:
            pass

    # ---------- Général ----------
    def _build_general_tab(self):
        """Construit l'onglet Général (cartes + état vide)."""
        self.general_page = 0

        self.tab_general.columnconfigure(0, weight=1)
        self.tab_general.rowconfigure(0, weight=0)
        self.tab_general.rowconfigure(1, weight=1)

        # Barre du haut (navigation pages)
        head = ttk.Frame(self.tab_general)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)

        # --- Zone droite : navigation pages (ton code existant) ---
        nav = ttk.Frame(head)
        nav.grid(row=0, column=0, sticky="e")


        self.btn_prev = ttk.Button(nav, text="◀", width=3, command=self._general_prev_page)
        self.lbl_page = ttk.Label(nav, text="")
        self.btn_next = ttk.Button(nav, text="▶", width=3, command=self._general_next_page)

        self.btn_prev.grid(row=0, column=0, padx=(0, 6))
        self.lbl_page.grid(row=0, column=1, padx=(0, 6))
        self.btn_next.grid(row=0, column=2)

        # Zone cartes (aperçu véhicules)
        self.general_cards = ttk.Frame(self.tab_general)
        self.general_cards.grid(row=1, column=0, sticky="nsew", pady=(0, 0))
        self.general_cards.columnconfigure(0, weight=1)
        self.general_cards.columnconfigure(1, weight=1)
        self.general_cards.rowconfigure(0, weight=1)

        self.general_empty_frame = ttk.Frame(self.tab_general)
        self.general_empty_frame.grid(row=1, column=0, sticky="nsew", pady=(0, 0))
        self.general_empty_frame.columnconfigure(0, weight=1)
        self.general_empty_frame.rowconfigure(0, weight=1)

        empty_msg = (
            "Aucun véhicule enregistré.\n\n"
            "Pour commencer, ajoutez un véhicule dans Paramètres > Véhicules.\n\n"
            "L'aide est disponible dans Paramètres > Aide."
        )
        self.general_empty_label = ttk.Label(
            self.general_empty_frame,
            text=empty_msg,
            anchor="center",
            justify="center",
        )
        self.general_empty_label.grid(row=0, column=0, sticky="nsew")

        try:
            self.general_empty_frame.grid_remove()
        except Exception:
            pass
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
        selected = self.active_vehicle_id is not None and int(self.active_vehicle_id) == vid
        colors = getattr(self, "_ui_colors", {})
        accent = colors.get("ACCENT", "#66B3FF")
        panel = colors.get("BG", colors.get("PANEL", ""))
        card = ttk.Frame(self.general_cards, padding=(12, 6))
        card.grid(row=row, column=col, columnspan=colspan, sticky="nsew", padx=8, pady=(0, 4))
        self.general_cards.columnconfigure(col, weight=1)
        self.general_cards.rowconfigure(row, weight=1)
        card.columnconfigure(1, weight=1)

        card.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))
        title_lbl = ttk.Label(card, text=title, font=self.font_card_title, anchor="center")
        title_lbl.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))
        title_lbl.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 0))


        cons = conso_moy_l100(vid)
        cons_txt = (f"{_fmt_num(cons, 2)} L/100 km" if cons is not None else "—")
        conso_lbl = ttk.Label(card, text=f"Conso moy. : {cons_txt}", font=self.font_info2_bold, foreground="#66B3FF")
        conso_lbl.grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 4))
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
        bat_line.grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 6))
        bat_line.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        img = _load_vehicle_photo_tk(r["photo_file"], max_w=270, max_h=165)
        self._general_card_imgs[vid] = img
        photo_border = tk.Frame(card, bg=accent if selected else panel, padx=2, pady=2)
        photo_border.grid(row=3, column=0, sticky="nw")
        photo = ttk.Label(photo_border, text="(aucune photo)")
        photo.grid(row=0, column=0, sticky="nw")
        if img:
            photo.config(image=img, text="")
        photo_border.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))
        photo.bind("<Button-1>", lambda e, v=vid: self._select_vehicle_from_general(v))

        est = estimate_maintenance_cost_next_months(vid, horizon_months=6)
        est_txt = (f"{_fmt_num(est, 0)} €" if est is not None else "—")
        cost_lbl = ttk.Label(card, text=f"Coût à prévoir pour les 6 prochains mois ≃ {est_txt}", font=self.font_rem_item, foreground="#66B3FF")
        cost_lbl.grid(row=4, column=0, sticky="w", pady=(6, 0))
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
        reminders.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        reminders.columnconfigure(0, weight=1)
        ttk.Label(reminders, text="Rappels:", font=self.font_rem_title).grid(row=0, column=0, sticky="w", pady=(0, 2))

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

        actions = ttk.Frame(card)
        actions.grid(row=6, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(
            actions,
            text="+ Plein",
            command=lambda v=vid: self._quick_add_plein(v),
        ).grid(row=0, column=0, padx=(0, 8))
        ttk.Button(
            actions,
            text="+ Entretien",
            command=lambda v=vid: self._quick_add_entretien(v),
        ).grid(row=0, column=1)

    def _quick_add_plein(self, vehicle_id: int):
        self.active_vehicle_id = int(vehicle_id)
        self._refresh_all_tabs_after_vehicle_change(source="general_click")
        self._show_pleins()
        self.new_pl_date.set("")
        self.new_pl_km.set("")
        self.new_pl_litres.set("")
        self.new_pl_prix.set("")
        self.new_pl_total.set("")
        self.new_pl_lieu.set("")

    def _quick_add_entretien(self, vehicle_id: int):
        self.active_vehicle_id = int(vehicle_id)
        self._refresh_all_tabs_after_vehicle_change(source="general_click")
        self._show_entretiens()
        self.new_date.set("")
        self.new_km.set("")
        self.new_cost.set("")
        self.new_by.set("")
        self.new_vbat.set("")
        self.new_details.set("")

    # bouton combobox selecteur de themes

    def _on_theme_change(self, _evt=None) -> None:
        name = self.theme_var.get().strip()
        if not name:
            return

        self._theme_name = name
        self._apply_platform_theme()
        try:
            self._refresh_general_overview()
        except Exception:
            pass

        # petit refresh UI
        try:
            self.update_idletasks()
        except Exception:
            pass


    # ---------- Véhicules ----------
    def _on_veh_vehicle_change(self, _evt=None):
        idx = self.veh_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._veh_set_mode("view")
        self._refresh_all_tabs_after_vehicle_change(source="vehicules")

    def _on_settings_preco_vehicle_change(self, _evt=None):
        idx = self.settings_preco_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._refresh_all_tabs_after_vehicle_change(source="settings_preconisations")

    def _veh_set_mode(self, mode: str):
        self._veh_mode = mode
        editable = mode in ("add", "edit")
        state = "normal" if editable else "readonly"

        for ent in self.veh_entries.values():
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
            messagebox.showinfo("Photo", "Veuillez cliquer sur Ajouter ou Modifier pour changer la photo.")
            return

        path = filedialog.askopenfilename(
            title="Choisir une photo",
            filetypes=[
                ("Images (PNG/JPG/BMP)", "*.png *.jpg *.jpeg *.bmp"),
                ("PNG", "*.png"),
                ("JPG/JPEG", "*.jpg *.jpeg"),
                ("BMP", "*.bmp"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        if not path:
            return

        ext = os.path.splitext(path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".bmp"):
            messagebox.showwarning("Photo", "Format non supporté. Veuillez choisir une image PNG, JPG/JPEG ou BMP.")
            return

        self._veh_photo_src_path = path

        # Aperçu : on utilise Pillow pour supporter JPG/BMP (et PNG aussi)
        try:
            from PIL import Image, ImageTk, ImageOps  # type: ignore

            img = Image.open(path)
            try:
                img = ImageOps.exif_transpose(img)
            except Exception:
                pass
            img = img.convert("RGBA")
            img.thumbnail((260, 120))

            tkimg = ImageTk.PhotoImage(img)
            self._veh_photo_img = tkimg  # garder une ref
            self.veh_photo_label.config(image=tkimg, text="")
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

        existing = get_vehicle(self.active_vehicle_id) if self._veh_mode == "edit" else None
        photo_file = existing["photo_file"] if existing else None

        if self._veh_mode == "add":
            # 1) Crée d'abord le véhicule pour obtenir un ID stable (sert aussi à nommer la photo)
            vid = insert_vehicle(nom, marque, modele, motorisation, energie, annee, immat, photo_file=None)
            self.active_vehicle_id = vid

            # 2) Si une photo a été choisie : copie avec un nom stable V<ID>.png, puis update
            if self._veh_photo_src_path:
                try:
                    photo_file = _copy_vehicle_photo(self._veh_photo_src_path, vid)
                except Exception as e:
                    messagebox.showerror("Photo", str(e))
                    photo_file = None

            update_vehicle(vid, nom, marque, modele, motorisation, energie, annee, immat, photo_file=photo_file)
            self._set_status("Véhicule ajouté.")

        else:
            # Edition : si nouvelle photo choisie, on écrase V<ID>.png
            if self._veh_photo_src_path:
                try:
                    photo_file = _copy_vehicle_photo(self._veh_photo_src_path, self.active_vehicle_id)
                except Exception as e:
                    messagebox.showerror("Photo", str(e))
                    return

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
            self.active_vehicle_id = None
            self._refresh_all()
            self._set_status("Plus aucun véhicule.")
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

        ttk.Label(form, text="Astuce : laissez le Total vide pour calcul auto (Litres × Prix/L).").grid(row=2, column=0, columnspan=5, sticky="w", pady=(8, 0))

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
        self.tab_ent.columnconfigure(0, weight=1, minsize=520)

        # Permet au tableau des entretiens (au centre) de s\'étendre, tout en gardant le formulaire visible en bas
        # Répartition verticale : on garantit une hauteur mini pour la liste "Entretiens"
        self.tab_ent.rowconfigure(0, weight=0)               # header
        self.tab_ent.rowconfigure(1, weight=1, minsize=140)  # liste entretiens (prioritaire)
        self.tab_ent.rowconfigure(2, weight=0)               # formulaire

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

        list_box = ttk.Labelframe(self.tab_ent, text="Entretiens", padding=10)
        list_box.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        list_box.columnconfigure(0, weight=1)
        list_box.rowconfigure(0, weight=1, minsize=90)

        cols = ("id", "date", "km", "type", "kind", "cout", "by", "vbat", "details")

        # --- Frame technique : Treeview + scrollbars (pour que les barres restent visibles en fenêtre étroite) ---
        tv_frame = ttk.Frame(list_box)
        tv_frame.grid(row=0, column=0, sticky="nsew")
        tv_frame.columnconfigure(0, weight=1)
        tv_frame.rowconfigure(0, weight=1)

        self.tree_ent = ttk.Treeview(tv_frame, columns=cols, show="headings", height=10)
        self.tree_ent.grid(row=0, column=0, sticky="nsew")

        heads = {
            "id": "ID", "date": "Date", "km": "Km", "type": "Type d'entretien",
            "kind": "Type intervention", "cout": "Coût €", "by": "Effectué par", "vbat": "Vbat", "details": "Détails"
        }
        widths = {"id": 50, "date": 90, "km": 80, "type": 170, "kind": 150, "cout": 80, "by": 130, "vbat": 60, "details": 300}
        minwidths = {"id": 50, "date": 90, "km": 80, "type": 140, "kind": 140, "cout": 80, "by": 100, "vbat": 60, "details": 240}
        for c in cols:
            self.tree_ent.heading(c, text=heads[c])
            self.tree_ent.column(c, width=widths[c], minwidth=minwidths[c], anchor="w", stretch=c in ("type", "kind", "by", "details"))

        ysb = ttk.Scrollbar(tv_frame, orient="vertical", command=self.tree_ent.yview)
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
        form.grid(row=2, column=0, sticky="ew", pady=(12, 0))
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

    # ---------- Graphiques ----------
    def _build_graphs_tab(self):
        self.tab_graphs.columnconfigure(0, weight=1)
        self.tab_graphs.rowconfigure(2, weight=1)

        header = ttk.Frame(self.tab_graphs)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="Véhicule :").grid(row=0, column=0, sticky="w")
        self.graph_vehicle_var = tk.StringVar(value="")
        self.graph_vehicle_cb = ttk.Combobox(header, textvariable=self.graph_vehicle_var, state="readonly")
        self.graph_vehicle_cb.grid(row=0, column=1, sticky="ew", padx=(10, 0))
        self.graph_vehicle_cb.bind("<<ComboboxSelected>>", self._on_graph_vehicle_change)

        controls = ttk.Frame(self.tab_graphs)
        controls.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Vue :").grid(row=0, column=0, sticky="w")

        self.graph_choice_var = tk.StringVar(value="Tous (3 graphes)")
        self.graph_choice_cb = ttk.Combobox(
            controls,
            textvariable=self.graph_choice_var,
            state="readonly",
            values=[
                "Tous (3 graphes)",
                "1) Conso (L/100 km)",
                "2) Prix du litre",
                "3) Coût entretien (€/an)",
            ],
            width=24,
        )
        self.graph_choice_cb.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.graph_choice_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_graph())

        # Seuil de masquage conso (appliqué au graphe 1)
        ttk.Label(controls, text="Conso :").grid(row=0, column=2, sticky="e", padx=(10, 0))
        self.conso_mask_var = tk.StringVar(value="Masquer au-dessus de 15 L/100")
        self.conso_mask_cb = ttk.Combobox(
            controls,
            textvariable=self.conso_mask_var,
            state="readonly",
            values=[
                "Masquer au-dessus de 10 L/100",
                "Masquer au-dessus de 15 L/100",
                "Masquer au-dessus de 20 L/100",
                "Masquer au-dessus de 25 L/100",
            ],
            width=26,
        )
        self.conso_mask_cb.grid(row=0, column=3, sticky="e", padx=(10, 0))
        self.conso_mask_cb.bind("<<ComboboxSelected>>", lambda _e: self._refresh_graph())

        # Zone de rendu
        self.graph_area = ttk.Frame(self.tab_graphs)
        self.graph_area.grid(row=2, column=0, sticky="nsew", pady=(12, 0))
        self.graph_area.columnconfigure(0, weight=1)
        self.graph_area.rowconfigure(0, weight=1)

        if not _ensure_matplotlib_available() or Figure is None or FigureCanvasTkAgg is None:
            details = f"\n\nDétail: {MATPLOTLIB_ERROR}" if MATPLOTLIB_ERROR else ""
            ttk.Label(
                self.graph_area,
                text=f"Matplotlib/Tk indisponible. Les graphiques ne peuvent pas être affichés.{details}",
                wraplength=900,
                justify="left",
            ).grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
            return

        self._graph_fig = Figure(figsize=(7.2, 7.6), dpi=100)
        # 3 axes empilés (une seule page)
        self._graph_axes = list(self._graph_fig.subplots(nrows=3, ncols=1, sharex=False))
        self._graph_ax = self._graph_axes[0]  # compat

        self._graph_canvas = FigureCanvasTkAgg(self._graph_fig, master=self.graph_area)
        self._graph_canvas_widget = self._graph_canvas.get_tk_widget()
        self._graph_canvas_widget.grid(row=0, column=0, sticky="nsew")

        # Toolbar (optionnelle)
        if NavigationToolbar2Tk is not None:
            toolbar = NavigationToolbar2Tk(self._graph_canvas, self.tab_graphs, pack_toolbar=False)
            toolbar.update()
            toolbar.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))

        self._refresh_graph()

    def _on_graph_vehicle_change(self, _evt=None):
        idx = self.graph_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._refresh_all_tabs_after_vehicle_change(source="graphs")

    def _refresh_graph(self):
        if not MATPLOTLIB_AVAILABLE or Figure is None or getattr(self, "_graph_canvas", None) is None:
            return
        if self.active_vehicle_id is None:
            return

        fig = self._graph_fig
        axes = getattr(self, "_graph_axes", None) or [self._graph_ax]

        # Figure dark
        fig.patch.set_facecolor("#1e1e1e")

        # Clear all axes and reset default positions later
        for ax in axes:
            ax.clear()
            ax.set_aspect("auto")

        choice = (self.graph_choice_var.get() or "").strip()
        # parse conso mask
        max_l100 = 15.0
        try:
            s = (self.conso_mask_var.get() or "")
            m = re.search(r"(\d+)", s)
            if m:
                max_l100 = float(m.group(1))
        except Exception:
            max_l100 = 15.0

        def hide(ax):
            ax.clear()
            ax.set_axis_off()

        if choice == "Tous (3 graphes)":
            # positions standard: 3 lignes
            for ax in axes:
                ax.set_axis_on()

            self._plot_conso_per_fill(axes[0], max_l100=max_l100)
            self._plot_price_per_litre(axes[1])
            self._plot_entretien_cost_per_year(axes[2])

            # layout stable
            fig.subplots_adjust(left=0.08, right=0.98, top=0.98, bottom=0.06, hspace=0.35)

        elif choice == "1) Conso (L/100 km)":
            axes[0].set_axis_on()
            self._plot_conso_per_fill(axes[0], max_l100=max_l100)
            # agrandir axe 0
            axes[0].set_position([0.08, 0.10, 0.90, 0.86])
            for ax in axes[1:]:
                hide(ax)

        elif choice == "2) Prix du litre":
            axes[0].set_axis_on()
            self._plot_price_per_litre(axes[0])
            axes[0].set_position([0.08, 0.10, 0.90, 0.86])
            for ax in axes[1:]:
                hide(ax)

        elif choice == "3) Coût entretien (€/an)":
            axes[0].set_axis_on()
            self._plot_entretien_cost_per_year(axes[0])
            axes[0].set_position([0.08, 0.10, 0.90, 0.86])
            for ax in axes[1:]:
                hide(ax)

        else:
            axes[0].set_axis_on()
            self._apply_dark_style(axes[0])
            self._title_in_ax(axes[0], "Graphiques")
            axes[0].text(0.5, 0.5, "Vue inconnue.", ha="center", va="center", transform=axes[0].transAxes, color="#dddddd")
            axes[0].set_position([0.08, 0.10, 0.90, 0.86])
            for ax in axes[1:]:
                hide(ax)

        self._graph_canvas.draw_idle()



    def _apply_dark_style(self, ax):
        """Applique un style sombre (idempotent) à un axe Matplotlib."""
        ax.set_facecolor("#1e1e1e")
        ax.tick_params(colors="#dddddd")
        ax.xaxis.label.set_color("#dddddd")
        ax.yaxis.label.set_color("#dddddd")
        # Grille discrète
        ax.grid(True, axis="y", linestyle=":", linewidth=0.6, alpha=0.30)
        # Spines
        for sp in ax.spines.values():
            sp.set_color("#777777")
        ax.title.set_color("#dddddd")



    def _title_in_ax(self, ax, text_label):
        """Titre placé dans le graphe, en haut à gauche."""
        ax.set_title("")
        ax.text(
            0.01, 0.99, text_label,
            transform=ax.transAxes,
            ha="left", va="top",
            fontsize=10,
            color="#dddddd",
            bbox=dict(boxstyle="round,pad=0.25", facecolor="#000000", edgecolor="#666666", alpha=0.35),
        )

    def _plot_conso_per_fill(self, ax, max_l100=15.0):
        """Conso (L/100) robuste (moyenne par blocs de km) + masquage des pics."""
        self._apply_dark_style(ax)
        self._title_in_ax(ax, "Conso (L/100 km)")

        WINDOW_KM = 200  # bloc de distance pour calcul représentatif

        rows = list_fill_consumption_points(self.active_vehicle_id)

        if not rows or len(rows) < 2:
            ax.text(0.5, 0.5, "Pas assez de pleins (>= 2).", ha="center", va="center",
                    transform=ax.transAxes, color="#dddddd")
            ax.set_ylabel("L/100 km")
            ax.set_xlabel("")
            return

        xs = []
        ys = []
        masked = 0

        prev_km = None
        km_cum = 0.0
        litres_cum = 0.0

        for r in rows:
            km = _safe_int(r["km"])
            litres = _safe_float(r["litres"])
            if km is None or litres is None:
                continue

            if prev_km is None:
                prev_km = km
                continue

            dkm = km - prev_km
            prev_km = km
            if dkm <= 0:
                continue

            km_cum += float(dkm)
            litres_cum += float(litres)

            if km_cum >= float(WINDOW_KM):
                conso = (litres_cum / km_cum) * 100.0
                if conso > float(max_l100):
                    masked += 1
                else:
                    d = _parse_iso_date(r["date_iso"])
                    xs.append(d if d else km)
                    ys.append(conso)

                km_cum = 0.0
                litres_cum = 0.0

        if not xs:
            ax.text(
                0.5, 0.5,
                f"Données insuffisantes (ou tout masqué).\nAstuce : baisse WINDOW_KM ou augmente le seuil.",
                ha="center", va="center", transform=ax.transAxes, color="#dddddd"
            )
            ax.set_ylabel("L/100 km")
            ax.set_xlabel("")
            return

        line = ax.plot(xs, ys, marker="o", linewidth=2)[0]

        ax.set_ylabel("L/100 km")
        ax.set_xlabel("")

        # rotation si dates
        try:
            for tick in ax.get_xticklabels():
                tick.set_rotation(20)
                tick.set_ha("right")
        except Exception:
            pass

        # Compteur points masqués (bas droite)
        if masked:
            ax.text(
                0.99, 0.01,
                f"{masked} point(s) masqué(s) (> {float(max_l100):.0f} L/100)",
                transform=ax.transAxes,
                ha="right", va="bottom",
                fontsize=8,
                color="#bbbbbb",
            )

    def _plot_price_per_litre(self, ax):
        self._apply_dark_style(ax)

        # Titre adapté à l'énergie du véhicule
        energie = ""
        try:
            v = get_vehicle(int(self.active_vehicle_id))
            energie = (v["energie"] or "").strip()
        except Exception:
            energie = ""

        def _fuel_phrase(e: str) -> str:
            e_low = e.lower()
            if any(k in e_low for k in ("ess", "sp95", "sp98", "e10")):
                return "d’essence"
            if any(k in e_low for k in ("dies", "gazo", "gasoil", "gazole")):
                return "de gasoil"
            if "e85" in e_low:
                return "d’E85"
            if "gpl" in e_low:
                return "de GPL"
            # fallback générique
            return "d’" + e if e[:1].lower() in "aeiouyàâäéèêëîïôöùûüœ" else "de " + e

        if energie:
            self._title_in_ax(ax, f"Prix du litre {_fuel_phrase(energie)} dans le temps")
        else:
            self._title_in_ax(ax, "Prix du litre dans le temps")

        rows = list_fuel_price_points(self.active_vehicle_id)

        if not rows:
            ax.text(0.5, 0.5, "Aucun plein avec prix/L à tracer.", ha="center", va="center",
                    transform=ax.transAxes, color="#dddddd")
            ax.set_ylabel("€/L")
            ax.set_xlabel("")
            return

        xs, ys = [], []
        for r in rows:
            d = _parse_iso_date(r["date_iso"])
            v = _safe_float(r["prix_litre"])
            if d is None or v is None:
                continue
            xs.append(d)
            ys.append(v)

        if not xs:
            ax.text(0.5, 0.5, "Données insuffisantes.", ha="center", va="center",
                    transform=ax.transAxes, color="#dddddd")
            ax.set_ylabel("€/L")
            ax.set_xlabel("")
            return

        ax.plot(xs, ys, marker="o", linewidth=2)
        ax.set_ylabel("€/L")
        ax.set_xlabel("")
        for tick in ax.get_xticklabels():
            tick.set_rotation(20)
            tick.set_ha("right")



    def _plot_entretien_cost_per_year(self, ax):
        """Coût entretien par an, séparé Entretiens vs Réparations."""
        self._apply_dark_style(ax)
        self._title_in_ax(ax, "Coût entretien (€/an)")

        rows = list_maintenance_cost_points(self.active_vehicle_id)

        if not rows:
            ax.text(
                0.5, 0.5, "Aucun entretien avec coût à tracer.",
                ha="center", va="center", transform=ax.transAxes, color="#dddddd"
            )
            ax.set_ylabel("€")
            ax.set_xlabel("")
            return

        import unicodedata

        def norm(s):
            if s is None:
                return ""
            s = str(s)
            s = unicodedata.normalize("NFKD", s)
            s = "".join(ch for ch in s if not unicodedata.combining(ch))
            return s.lower().strip()

        repair_keys = (
            "repar", "depann", "panne", "casse", "diagnost", "garagiste", "garage",
            "embrayage", "turbo", "inject", "pompe", "alternat", "demarreur",
            "joint", "culasse", "boite", "distribution", "radiateur", "amortisseur",
            "triangle", "rotule", "roulement", "cardan", "fuite", "freinage"
        )

        def is_repair(r):
            # sqlite3.Row -> accès par index/nom (pas .get)
            kind = norm(r["kind"]) if "kind" in r.keys() else ""
            inter = norm(r["intervention"]) if "intervention" in r.keys() else ""
            det = norm(r["details"]) if "details" in r.keys() else ""
            blob = f"{kind} {inter} {det}"
            return any(k in blob for k in repair_keys)

        # Agrégation annuelle
        year_ent = {}
        year_rep = {}

        for r in rows:
            d = _parse_iso_date(r["date_iso"])
            if not d:
                continue
            y = int(d.year)
            try:
                cost = float(r["cout"])
            except Exception:
                continue

            if is_repair(r):
                year_rep[y] = year_rep.get(y, 0.0) + cost
            else:
                year_ent[y] = year_ent.get(y, 0.0) + cost

        years = sorted(set(year_ent.keys()) | set(year_rep.keys()))
        if not years:
            ax.text(
                0.5, 0.5, "Aucune donnée exploitable.",
                ha="center", va="center", transform=ax.transAxes, color="#dddddd"
            )
            ax.set_ylabel("€")
            ax.set_xlabel("")
            return

        ent_vals = [year_ent.get(y, 0.0) for y in years]
        rep_vals = [year_rep.get(y, 0.0) for y in years]

        import numpy as np
        x = np.arange(len(years), dtype=float)
        width = 0.38

        # Barres: couleurs fixées (bleu/orange) pour rester lisible
        bars_ent = ax.bar(x - width/2, ent_vals, width=width, color="#1f77b4", label="Entretiens")
        bars_rep = ax.bar(x + width/2, rep_vals, width=width, color="#ff7f0e", label="Réparations")

        ax.set_ylabel("€")
        ax.set_xlabel("")
        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in years], color="#dddddd")

        # suppression du trait qui donne l'impression d'un repere année precis   
        ax.tick_params(axis="x", which="both", length=0)

        # Légende en haut à droite, compacte
        leg = ax.legend(loc="upper right", frameon=True, fontsize=9)
        if leg and leg.get_frame():
            leg.get_frame().set_facecolor("#1e1e1e")
            leg.get_frame().set_edgecolor("#666666")
            leg.get_frame().set_alpha(0.6)

        def annotate(bars):
            for b in bars:
                h = float(b.get_height())
                if h <= 0:
                    continue

                ax.text(
                    b.get_x() + b.get_width()/2,
                    h / 2,              # <-- milieu vertical de la barre
                    f"{h:.0f}€",
                    ha="center",
                    va="center",        # <-- centré verticalement
                    fontsize=8,
                    color="#ffffff",    # plus lisible au milieu
                    fontweight="bold",
                )


        annotate(bars_ent)
        annotate(bars_rep)

        # Un peu d'air en bas pour les labels
        ax.set_ylim(bottom=0)

    def _plot_entretien_cost_per_month(self, ax):
        rows = list_maintenance_cost_by_month(self.active_vehicle_id)

        if not rows:
            ax.text(0.5, 0.5, "Aucun entretien avec coût à tracer.", ha="center", va="center")
            ax.set_title("Coût entretien par mois")
            return

        labels = []
        values = []
        for r in rows:
            ym = r["ym"]
            total = _safe_float(r["total"])
            if ym and total is not None:
                labels.append(ym)
                values.append(total)

        if not labels:
            ax.text(0.5, 0.5, "Données insuffisantes.", ha="center", va="center")
            ax.set_title("Coût entretien par mois")
            return

        ax.bar(labels, values)
        ax.set_title("Coût entretien par mois")
        ax.set_ylabel("€")
        ax.set_xlabel("Mois (YYYY-MM)")
        # Rotation légère pour lisibilité
        for tick in ax.get_xticklabels():
            tick.set_rotation(45)
            tick.set_ha("right")

    def _on_ent_vehicle_change(self, _evt=None):
        idx = self.ent_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._refresh_all_tabs_after_vehicle_change(source="entretiens")

    def _on_settings_maintenance_vehicle_change(self, _evt=None):
        idx = self.settings_maintenance_vehicle_cb.current()
        if idx is None or idx < 0:
            return
        self.active_vehicle_id = self._vehicle_index_to_id[idx]
        self._refresh_all_tabs_after_vehicle_change(source="settings_maintenance")

    def _refresh_types_ui(self):
        self.selected_type_id = None
        self.type_name_var.set("")
        self.type_km_var.set("")
        self.type_months_var.set("")
        self._type_name_to_id = {}

        for item in self.tree_types.get_children():
            self.tree_types.delete(item)

        if self.active_vehicle_id is None:
            return

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
        if self.active_vehicle_id is None:
            return
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
        if self.active_vehicle_id is None:
            self._type_name_to_id = {}
            self.new_type_cb["values"] = []
            self.new_type.set("")
            return
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

    def _show_empty_state(self):
        """État UI quand la base est vide (aucun véhicule)."""
        # Mettre les listes déroulantes à vide si elles existent
        for attr in ("veh_vehicle_cb", "pl_vehicle_cb", "ent_vehicle_cb", "graph_vehicle_cb", "settings_preco_vehicle_cb", "settings_maintenance_vehicle_cb"):
            cb = getattr(self, attr, None)
            if cb is not None:
                try:
                    cb["values"] = []
                    cb.set("")
                except Exception:
                    pass

        # Mettre les en-têtes à jour si présents
        for attr, text in (
            ("pl_header_label", "Aucun véhicule"),
            ("ent_header_label", "Aucun véhicule"),
        ):
            w = getattr(self, attr, None)
            if w is not None:
                try:
                    w.config(text=text)
                except Exception:
                    pass

        # Status bar
        try:
            self._set_status("")
        except Exception:
            pass

        # Basculer sur l'onglet Général et afficher l'état vide.
        try:
            self.tab_general.tkraise()
        except Exception:
            pass

        try:
            self.general_cards.grid_remove()
            self.general_empty_frame.grid()
        except Exception:
            pass

        try:
            self._refresh_preconisations()
        except Exception:
            pass
        try:
            self._refresh_types_ui()
            self._refresh_type_choices_for_new_entretien()
        except Exception:
            pass

    def _refresh_all(self):
        self.vehicles_rows = list_vehicles()
        if not self.vehicles_rows:
            self.active_vehicle_id = None
            self._vehicle_index_to_id = []
            self._show_empty_state()
            return

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
        self.graph_vehicle_cb["values"] = labels
        self.settings_preco_vehicle_cb["values"] = labels
        self.settings_maintenance_vehicle_cb["values"] = labels

        self._refresh_all_tabs_after_vehicle_change(source="init")

    def _refresh_all_tabs_after_vehicle_change(self, source=""):

        if not getattr(self, "_vehicle_index_to_id", None) or self.active_vehicle_id is None:
            self._show_empty_state()
            return

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
        if source != "graphs":
            self.graph_vehicle_cb.current(idx)
        if source != "settings_preconisations":
            self.settings_preco_vehicle_cb.current(idx)
        if source != "settings_maintenance":
            self.settings_maintenance_vehicle_cb.current(idx)

        try:
            self.general_empty_frame.grid_remove()
            self.general_cards.grid()
        except Exception:
            pass

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
        try:
            self._refresh_graph()
        except Exception:
            pass

        self._set_status("")


def main():
    app = GarageApp()
    app.mainloop()


if __name__ == "__main__":
    main()
