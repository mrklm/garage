import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
from pathlib import Path
import shutil
import time

APP_NAME = "Garage"
APP_VERSION = "2.1.0"

SCRIPT_DIR = Path(__file__).resolve().parent
DB_FILE = str(SCRIPT_DIR / "garage.db")

ASSETS_DIR = SCRIPT_DIR / "assets"
VEHICLES_DIR = ASSETS_DIR / "vehicles"

MAX_VEHICLES = 5

# Pillow optionnel
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


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
        if path is None:
            return None, "Pillow non disponible (et aucune photo définie)."
        if not path.exists():
            return None, f"{path} introuvable (et Pillow non disponible)."
        return None, f"Pillow non disponible: impossible d'afficher {path.name}."


def connect():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def table_columns(conn, table: str) -> set[str]:
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    return {row[1] for row in cur.fetchall()}


def ensure_vehicle(conn, nom: str, marque=None, modele=None, motorisation=None, energie=None, immatriculation=None, photo_filename=None) -> int:
    cur = conn.cursor()
    cur.execute("SELECT id FROM vehicules WHERE nom = ?", (nom,))
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur.execute(
        """
        INSERT INTO vehicules (nom, marque, modele, motorisation, energie, immatriculation, photo_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (nom, marque, modele, motorisation, energie, immatriculation, photo_filename),
    )
    conn.commit()
    return int(cur.lastrowid)


def init_db_and_migrate():
    ensure_dirs()
    conn = connect()
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS vehicules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL UNIQUE,
            marque TEXT,
            modele TEXT,
            motorisation TEXT,
            energie TEXT,
            immatriculation TEXT,
            photo_filename TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS lieux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )
        """
    )

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

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS app_config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """
    )

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
    conn.commit()

    cols = table_columns(conn, "pleins")
    if "vehicule" in cols and "vehicule_id" not in cols:
        cur.execute("ALTER TABLE pleins ADD COLUMN vehicule_id INTEGER")
        conn.commit()

        biche_id = ensure_vehicle(conn, nom="Biche")
        titine_id = ensure_vehicle(conn, nom="Titine")

        cur.execute("UPDATE pleins SET vehicule_id = ? WHERE vehicule = 0", (biche_id,))
        cur.execute("UPDATE pleins SET vehicule_id = ? WHERE vehicule = 1", (titine_id,))
        cur.execute("UPDATE pleins SET vehicule_id = ? WHERE vehicule_id IS NULL", (biche_id,))
        conn.commit()

    cur.execute("SELECT COUNT(*) FROM vehicules")
    if (cur.fetchone()[0] or 0) == 0:
        ensure_vehicle(conn, nom="Biche")
        ensure_vehicle(conn, nom="Titine")
        conn.commit()

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


def list_vehicles():
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, nom, marque, modele, motorisation, energie, immatriculation, photo_filename
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
        SELECT id, nom, marque, modele, motorisation, energie, immatriculation, photo_filename
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


def add_vehicle(nom, marque, modele, motorisation, energie, immatriculation, photo_filename):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vehicules (nom, marque, modele, motorisation, energie, immatriculation, photo_filename)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (nom, marque, modele, motorisation, energie, immatriculation, photo_filename),
    )
    conn.commit()
    new_id = int(cur.lastrowid)
    conn.close()
    return new_id


def update_vehicle(vehicle_id, nom, marque, modele, motorisation, energie, immatriculation, photo_filename):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE vehicules
        SET nom = ?, marque = ?, modele = ?, motorisation = ?, energie = ?, immatriculation = ?, photo_filename = ?
        WHERE id = ?
        """,
        (nom, marque, modele, motorisation, energie, immatriculation, photo_filename, vehicle_id),
    )
    conn.commit()
    conn.close()


def delete_vehicle(vehicle_id: int):
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pleins WHERE vehicule_id = ?", (vehicle_id,))
    n = int(cur.fetchone()[0] or 0)
    if n > 0:
        conn.close()
        raise ValueError(f"Suppression impossible : {n} plein(s) référencent ce véhicule.")
    cur.execute("DELETE FROM vehicules WHERE id = ?", (vehicle_id,))
    conn.commit()
    conn.close()


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
        SELECT id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire
        FROM pleins
        WHERE vehicule_id = ?
        ORDER BY date DESC, kilometrage DESC, id DESC
        """,
        (vehicle_id,),
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def add_plein(vehicle_id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO pleins (vehicule_id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vehicle_id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire),
    )
    conn.commit()
    conn.close()


def update_plein(plein_id, vehicle_id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire):
    conn = connect()
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE pleins
        SET vehicule_id = ?, date = ?, kilometrage = ?, litres = ?, prix_litre = ?, total = ?,
            lieu = ?, type_usage = ?, commentaire = ?
        WHERE id = ?
        """,
        (vehicle_id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire, plein_id),
    )
    conn.commit()
    conn.close()


def delete_plein(plein_id):
    conn = connect()
    cur = conn.cursor()
    cur.execute("DELETE FROM pleins WHERE id = ?", (plein_id,))
    conn.commit()
    conn.close()


def list_lieux():
    conn = connect()
    cur = conn.cursor()
    cur.execute("SELECT nom FROM lieux ORDER BY nom COLLATE NOCASE ASC")
    rows = cur.fetchall()
    conn.close()
    return [r[0] for r in rows]


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


class GarageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        init_db_and_migrate()

        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1300x720")

        self.vehicle_id_active: int | None = None
        self.plein_edit_id: int | None = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_pleins = ttk.Frame(self.notebook)
        self.tab_lieux = ttk.Frame(self.notebook)
        self.tab_vehicules = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_pleins, text="Pleins")
        self.notebook.add(self.tab_lieux, text="Lieux")
        self.notebook.add(self.tab_vehicules, text="Véhicules")

        self._create_menu()
        self._build_pleins_tab()
        self._build_lieux_tab()
        self._build_vehicules_tab()

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
            "Suivi des pleins multi-véhicules + gestion des lieux.\n\n"
            f"Base: {DB_FILE}\n"
            f"Photos: {VEHICLES_DIR}\n"
            f"Pillow: {'OK' if PIL_AVAILABLE else 'non détecté'}",
        )

    # ---- Pleins ----

    def _build_pleins_tab(self):
        top = tk.Frame(self.tab_pleins)
        top.pack(fill=tk.X, pady=10)

        left = tk.Frame(top)
        left.pack(side=tk.LEFT, padx=20)

        tk.Label(left, text="Véhicule").pack(anchor="w")
        self.cb_vehicle = ttk.Combobox(left, state="readonly", width=26)
        self.cb_vehicle.pack(anchor="w")
        self.cb_vehicle.bind("<<ComboboxSelected>>", self._on_vehicle_selected_from_combo)

        self.canvas_photo = tk.Canvas(left, width=220, height=150, highlightthickness=1)
        self.canvas_photo.pack(pady=6)

        # KM centered + bigger
        self.lbl_km = tk.Label(left, text="— km", font=("Arial", 14, "bold"))
        self.lbl_km.pack(fill=tk.X)

        center = tk.Frame(top)
        center.pack(side=tk.LEFT, expand=True)

        tk.Button(center, text="Ajouter / Enregistrer", command=self._on_save_plein, width=28).pack(pady=4)
        tk.Button(center, text="Modifier le plein sélectionné", command=self._on_load_selected_plein, width=28).pack(pady=4)
        tk.Button(center, text="Supprimer le plein sélectionné", command=self._on_delete_selected_plein, width=28).pack(pady=4)
        tk.Button(center, text="Importer un fichier (CSV)", command=self._import_csv, width=28).pack(pady=4)

        right = tk.Frame(top)
        right.pack(side=tk.RIGHT, padx=20)

        tk.Label(right, text="Infos véhicule").pack(anchor="w")
        self.vehicle_info_text = tk.Text(right, width=36, height=8, wrap="word")
        self.vehicle_info_text.pack()
        self.vehicle_info_text.configure(state="disabled")

        mid = tk.Frame(self.tab_pleins)
        mid.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ("id", "date", "km", "litres", "prix", "total", "lieu", "type_usage", "commentaire")
        self.tree = ttk.Treeview(mid, columns=columns, show="headings")

        widths = {"id": 50, "date": 90, "km": 80, "litres": 120, "prix": 90, "total": 90,
                  "lieu": 140, "type_usage": 160, "commentaire": 360}
        headings = {"id": "ID", "date": "Date", "km": "Km", "litres": "Nbre de Litres", "prix": "€ / Litre",
                    "total": "Total (€)", "lieu": "Lieu", "type_usage": "Type de Trajets", "commentaire": "Commentaire"}

        for col in columns:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, width=widths[col], stretch=(col == "commentaire"))

        self.tree.pack(fill=tk.BOTH, expand=True)

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
            ("Lieu", "lieu", 18),
            ("Type de Trajets", "type_usage", 18),
            ("Commentaire", "commentaire", 26),
        ]

        for i, (label, key, width) in enumerate(fields):
            tk.Label(form, text=label, font=("Arial", 12, "bold") if key == "prix" else None).grid(row=0, column=i, padx=3)
            if key == "lieu":
                cb = ttk.Combobox(form, state="readonly", width=width)
                cb.grid(row=1, column=i, padx=3)
                self.plein_entries[key] = cb
            elif key == "type_usage":
                cb = ttk.Combobox(form, state="readonly", width=width, values=["Trajets Quotidiens", "Longs Trajets"])
                cb.grid(row=1, column=i, padx=3)
                self.plein_entries[key] = cb
            else:
                e = tk.Entry(form, width=width)
                e.grid(row=1, column=i, padx=3)
                self.plein_entries[key] = e

        self._refresh_lieux_combo()

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

        self._refresh_vehicle_selector()
        self._apply_active_vehicle_to_ui()

    def _refresh_vehicle_selector(self):
        vehicles = list_vehicles()
        display = [row[1] for row in vehicles]  # nom seulement
        self._vehicle_name_to_id = {row[1]: int(row[0]) for row in vehicles}
        self.cb_vehicle["values"] = display

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

    def _on_vehicle_selected_from_combo(self, _evt=None):
        name = self.cb_vehicle.get()
        vid = self._vehicle_name_to_id.get(name)
        if vid is None:
            return
        self.vehicle_id_active = vid
        set_config("active_vehicle_id", str(vid))
        self.plein_edit_id = None
        self._clear_plein_form()
        self._apply_active_vehicle_to_ui()

    def _apply_active_vehicle_to_ui(self):
        self._refresh_vehicle_photo_and_info()
        self._refresh_pleins()
        self._refresh_km_label()

    def _refresh_vehicle_photo_and_info(self):
        v = get_vehicle(self.vehicle_id_active) if self.vehicle_id_active else None
        if not v:
            return
        _, nom, marque, modele, motorisation, energie, immat, photo = v

        self.canvas_photo.delete("all")
        tk_img, _err = load_photo_or_placeholder(photo, size=(220, 150), label=nom)
        self._tk_vehicle_photo = tk_img
        if tk_img is not None:
            self.canvas_photo.create_image(0, 0, anchor="nw", image=tk_img)
        else:
            self.canvas_photo.create_rectangle(0, 0, 220, 150, fill="#c8c8c8", outline="#999999")
            self.canvas_photo.create_text(110, 75, text=f"{nom}\nPhoto introuvable", justify="center")

        lines = []
        if marque: lines.append(f"Marque : {marque}")
        if modele: lines.append(f"Modèle : {modele}")
        if motorisation: lines.append(f"Motorisation : {motorisation}")
        if energie: lines.append(f"Énergie : {energie}")
        if immat: lines.append(f"Immatriculation : {immat}")

        self.vehicle_info_text.configure(state="normal")
        self.vehicle_info_text.delete("1.0", "end")
        self.vehicle_info_text.insert("1.0", "\n".join(lines) if lines else "(aucune info renseignée)")
        self.vehicle_info_text.configure(state="disabled")

    def _refresh_km_label(self):
        km = last_km(self.vehicle_id_active) if self.vehicle_id_active else None
        self.lbl_km.config(text=f"{km if km is not None else '—'} km")

    def _refresh_pleins(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not self.vehicle_id_active:
            return
        rows = list_pleins(self.vehicle_id_active)
        for (pid, date_iso, km, litres, prix, total, lieu, type_usage, commentaire) in rows:
            try:
                an, mois, jour = date_iso.split("-")
                date_aff = f"{jour}/{mois}/{an[2:]}"
            except Exception:
                date_aff = date_iso
            self.tree.insert("", "end", values=(pid, date_aff, km, f"{litres:.2f}", f"{prix:.3f}", f"{total:.2f}",
                                                lieu or "", type_usage or "", commentaire or ""))

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
            last = last_km(self.vehicle_id_active, exclude_id=self.plein_edit_id)
            if last is not None and km < last:
                raise ValueError(f"Kilométrage incohérent : {km} km < dernier relevé ({last} km).")

            litres = float(self.plein_entries["litres"].get().replace(",", "."))
            prix = float(self.plein_entries["prix"].get().replace(",", "."))
            total = litres * prix

            lieu = (self.plein_entries["lieu"].get() or "").strip()
            type_usage = (self.plein_entries["type_usage"].get() or "").strip()
            commentaire = (self.plein_entries["commentaire"].get() or "").strip()

            if self.plein_edit_id is None:
                add_plein(self.vehicle_id_active, date_iso, km, litres, prix, total, lieu, type_usage, commentaire)
            else:
                update_plein(self.plein_edit_id, self.vehicle_id_active, date_iso, km, litres, prix, total, lieu, type_usage, commentaire)
                self.plein_edit_id = None

            self._refresh_pleins()
            self._refresh_km_label()
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
            if "/" in date_val:
                jour, mois, an = date_val.split("/")
            else:
                an, mois, jour = date_val.split("-")
                an = an[2:]
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
        self.plein_entries["type_usage"].set(values[7])
        self.plein_entries["commentaire"].insert(0, values[8])

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
        self._refresh_km_label()
        self._clear_plein_form()

    def _import_csv(self):
        messagebox.showinfo("Importer CSV", "Fonction à venir (v2+).")

    # ---- Lieux ----

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
        current = cb.get()
        cb["values"] = lieux
        cb.set(current if current in lieux else "")

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

    # ---- Véhicules ----

    def _build_vehicules_tab(self):
        container = tk.Frame(self.tab_vehicules)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left = tk.Frame(container)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        right = tk.Frame(container)
        right.pack(side=tk.LEFT, fill=tk.Y, padx=30)

        tk.Label(left, text=f"Véhicules (max {MAX_VEHICLES}) :").pack(anchor="w")
        self.tree_vehicles = ttk.Treeview(left, columns=("id", "nom", "marque", "modele", "energie"), show="headings")
        for c, w in [("id", 50), ("nom", 160), ("marque", 140), ("modele", 140), ("energie", 120)]:
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
        add_field("Immatriculation", "immat", 5)

        tk.Label(form, text="Photo").grid(row=6, column=0, sticky="w", pady=3)
        self.lbl_photo = tk.Label(form, text="(aucune)")
        self.lbl_photo.grid(row=6, column=1, sticky="w", pady=3)
        tk.Button(form, text="Choisir…", command=self._pick_vehicle_photo).grid(row=7, column=1, sticky="w", pady=3)

        self.canvas_vehicle_preview = tk.Canvas(right, width=240, height=160, highlightthickness=1)
        self.canvas_vehicle_preview.pack(pady=10)

        actions = tk.Frame(right)
        actions.pack(fill=tk.X, pady=10)

        tk.Button(actions, text="Ajouter", command=self._on_vehicle_add, width=18).grid(row=0, column=0, pady=4, padx=4)
        tk.Button(actions, text="Enregistrer", command=self._on_vehicle_save, width=18).grid(row=0, column=1, pady=4, padx=4)
        tk.Button(actions, text="Supprimer", command=self._on_vehicle_delete, width=18).grid(row=1, column=0, pady=4, padx=4)
        tk.Button(actions, text="Définir actif", command=self._on_vehicle_set_active, width=18).grid(row=1, column=1, pady=4, padx=4)
        tk.Button(actions, text="Rafraîchir", command=self._refresh_all_vehicles_ui, width=18).grid(row=2, column=0, pady=4, padx=4)

        self._vehicle_selected_id: int | None = None
        self._vehicle_selected_photo_filename: str | None = None
        self._clear_vehicle_form()

    def _refresh_all_vehicles_ui(self):
        for item in self.tree_vehicles.get_children():
            self.tree_vehicles.delete(item)

        vehicles = list_vehicles()
        for (vid, nom, marque, modele, motorisation, energie, immat, photo) in vehicles:
            self.tree_vehicles.insert("", "end", values=(vid, nom, marque or "", modele or "", energie or ""))

        if hasattr(self, "cb_vehicle"):
            if self.vehicle_id_active is None and vehicles:
                self.vehicle_id_active = int(vehicles[0][0])
            self._refresh_vehicle_selector()
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
        _, nom, marque, modele, motorisation, energie, immat, photo = v
        self._vehicle_selected_photo_filename = photo

        self.vehicle_form["nom"].delete(0, tk.END); self.vehicle_form["nom"].insert(0, nom or "")
        self.vehicle_form["marque"].delete(0, tk.END); self.vehicle_form["marque"].insert(0, marque or "")
        self.vehicle_form["modele"].delete(0, tk.END); self.vehicle_form["modele"].insert(0, modele or "")
        self.vehicle_form["motorisation"].delete(0, tk.END); self.vehicle_form["motorisation"].insert(0, motorisation or "")
        self.vehicle_form["energie"].delete(0, tk.END); self.vehicle_form["energie"].insert(0, energie or "")
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

        try:
            if self._vehicle_selected_id is None:
                if count_vehicles() >= MAX_VEHICLES:
                    messagebox.showwarning("Véhicules", f"Limite atteinte ({MAX_VEHICLES}).")
                    return
                new_id = add_vehicle(nom, marque, modele, motorisation, energie, immat, photo)
                self._vehicle_selected_id = new_id
                if self.vehicle_id_active is None:
                    self.vehicle_id_active = new_id
                    set_config("active_vehicle_id", str(new_id))
            else:
                update_vehicle(self._vehicle_selected_id, nom, marque, modele, motorisation, energie, immat, photo)

        except sqlite3.IntegrityError:
            messagebox.showerror("Véhicule", "Ce nom existe déjà. Choisis un pseudo différent.")
            return
        except Exception as e:
            messagebox.showerror("Véhicule", str(e))
            return

        self._refresh_all_vehicles_ui()
        self._update_vehicle_photo_labels_and_preview(photo)

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
        self.vehicle_id_active = self._vehicle_selected_id
        set_config("active_vehicle_id", str(self.vehicle_id_active))
        self._refresh_vehicle_selector()
        self._apply_active_vehicle_to_ui()
        self.notebook.select(self.tab_pleins)


if __name__ == "__main__":
    app = GarageApp()
    app.mainloop()
