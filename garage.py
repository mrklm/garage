import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
import sqlite3
from pathlib import Path

# Images (mettez vos fichiers ici)
# Dossier attendu: ./assets à côté de ce script
SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR / "assets"

# Base SQLite stockée à côté du script (chemin robuste)
DB_FILE = str(SCRIPT_DIR / "garage.db")

APP_NAME = "Garage"
APP_VERSION = "0.9.2"

# Pillow optionnel (si absent, on affiche un placeholder texte)
try:
    from PIL import Image, ImageTk, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def load_photo_or_placeholder(filename: str, size=(180, 120), label="Véhicule"):
    """
    Charge une image depuis ASSETS_DIR/filename.
    Si absent/illisible: renvoie un placeholder grisé avec message.
    """
    w, h = size
    path = ASSETS_DIR / filename

    if PIL_AVAILABLE:
        try:
            img = Image.open(path).convert("RGBA").resize((w, h))
            return ImageTk.PhotoImage(img), None
        except Exception as e:
            img = Image.new("RGBA", (w, h), (200, 200, 200, 255))
            draw = ImageDraw.Draw(img)
            draw.line((0, 0, w, h), fill=(150, 150, 150, 255), width=4)
            draw.line((0, h, w, 0), fill=(150, 150, 150, 255), width=4)
            text = f"{label}\nImage introuvable"
            try:
                font = ImageFont.load_default()
            except Exception:
                font = None
            bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            draw.multiline_text(((w - tw) / 2, (h - th) / 2), text, fill=(60, 60, 60, 255), font=font, align="center")
            return ImageTk.PhotoImage(img), f"{path} : {e}"
    else:
        # Fallback sans Pillow: on met un "visuel" simple sur Canvas
        # On renverra None pour l'image, et l'appelant dessinera le texte.
        if path.exists():
            return None, f"Pillow n'est pas disponible: impossible d'afficher {path.name}."
        return None, f"{path} introuvable (et Pillow non disponible)."


# =========================
# Base de données (SQLite)
# =========================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pleins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicule INTEGER NOT NULL,
            date TEXT NOT NULL,
            kilometrage INTEGER NOT NULL,
            litres REAL NOT NULL,
            prix_litre REAL NOT NULL,
            total REAL NOT NULL,
            lieu TEXT,
            type_usage TEXT,
            commentaire TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lieux (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT UNIQUE NOT NULL
        )
        """
    )

    cursor.execute(
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
    conn.close()


def dernier_kilometrage(vehicule: int, exclude_id=None):
    """Retourne le dernier kilométrage (MAX) pour un véhicule, en excluant éventuellement un plein."""
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    if exclude_id is None:
        cur.execute("SELECT MAX(kilometrage) FROM pleins WHERE vehicule = ?", (vehicule,))
    else:
        cur.execute(
            "SELECT MAX(kilometrage) FROM pleins WHERE vehicule = ? AND id <> ?",
            (vehicule, exclude_id),
        )
    res = cur.fetchone()
    conn.close()
    return int(res[0]) if res and res[0] is not None else None


def ajouter_plein(vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO pleins (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire),
    )
    conn.commit()
    conn.close()


def modifier_plein(plein_id, vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE pleins
        SET vehicule = ?,
            date = ?,
            kilometrage = ?,
            litres = ?,
            prix_litre = ?,
            total = ?,
            lieu = ?,
            type_usage = ?,
            commentaire = ?
        WHERE id = ?
        """,
        (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire, plein_id),
    )
    conn.commit()
    conn.close()


def lister_pleins(vehicule):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire
        FROM pleins
        WHERE vehicule = ?
        ORDER BY date DESC, kilometrage DESC, id DESC
        """,
        (vehicule,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def supprimer_plein(plein_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pleins WHERE id = ?", (plein_id,))
    conn.commit()
    conn.close()


def lister_lieux():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nom FROM lieux ORDER BY nom ASC")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]


def ajouter_lieu(nom: str):
    nom = (nom or "").strip()
    if not nom:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO lieux (nom) VALUES (?)", (nom,))
    conn.commit()
    conn.close()


def compter_pleins_pour_lieu(nom: str) -> int:
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM pleins WHERE lieu = ?", (nom,))
    n = int(cur.fetchone()[0] or 0)
    conn.close()
    return n


def supprimer_lieu(nom: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lieux WHERE nom = ?", (nom,))
    conn.commit()
    conn.close()


def renommer_lieu(ancien: str, nouveau: str):
    ancien = (ancien or "").strip()
    nouveau = (nouveau or "").strip()
    if not ancien or not nouveau:
        raise ValueError("Ancien et nouveau nom doivent être renseignés.")
    if ancien == nouveau:
        return

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    try:
        cur.execute("BEGIN")
        # Met à jour la table lieux
        cur.execute("UPDATE lieux SET nom = ? WHERE nom = ?", (nouveau, ancien))
        if cur.rowcount == 0:
            cur.execute("INSERT OR IGNORE INTO lieux (nom) VALUES (?)", (nouveau,))
        # Met à jour les pleins existants
        cur.execute("UPDATE pleins SET lieu = ? WHERE lieu = ?", (nouveau, ancien))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.rollback()
        raise ValueError(f"Le lieu '{nouveau}' existe déjà.")
    finally:
        conn.close()


# =========================
# Interface graphique
# =========================

class GarageApp(tk.Tk):
    def create_menu(self):
        menubar = tk.Menu(self)

        menu_aide = tk.Menu(menubar, tearoff=0)
        menu_aide.add_command(label="À propos…", command=self.on_about)
        menubar.add_cascade(label="Aide", menu=menu_aide)

        self.config(menu=menubar)

    def on_about(self):
        messagebox.showinfo(
            "À propos",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "Gestion des pleins, lieux et suivi kilométrique (2 véhicules).\n\n"
            f"Base: {DB_FILE}\n"
            f"Images: {ASSETS_DIR}",
        )

    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry("1200x650")

        init_db()

        self.vehicule_actif = 0
        self.plein_en_cours = None  # id du plein en cours de modification

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_pleins = ttk.Frame(self.notebook)
        self.tab_lieux = ttk.Frame(self.notebook)

        self.notebook.add(self.tab_pleins, text="Pleins")
        self.notebook.add(self.tab_lieux, text="Lieux")

        self.create_menu()
        self.create_top_bar()     # photos gauche/droite + boutons au centre
        self.create_main_area()   # tableau + champs en bas (comme l'ancienne version)
        self.create_lieux_tab()

        self.refresh_lieux_ui()
        self.set_vehicule_actif(0)

        # Alerte si dossier assets absent
        if not ASSETS_DIR.exists():
            messagebox.showwarning(
                "Images",
                f"Dossier images introuvable:\n{ASSETS_DIR}\n\n"
                "Créez-le et ajoutez:\n"
                "- Biche.png\n"
                "- Titine.png",
            )

    # ---------------------
    # Onglet Pleins - Haut
    # ---------------------

    def create_top_bar(self):
        top = tk.Frame(self.tab_pleins)
        top.pack(fill=tk.X, pady=10)

        # Biche (gauche)
        frame_left = tk.Frame(top)
        frame_left.pack(side=tk.LEFT, padx=30)

        self.tk_biche, err_biche = load_photo_or_placeholder("Biche.png", (180, 120), "Biche")
        self._img_error_biche = err_biche

        self.canvas_biche = tk.Canvas(frame_left, width=180, height=120, highlightthickness=3)
        self.canvas_biche.pack()
        if self.tk_biche is not None:
            self.canvas_biche.create_image(0, 0, anchor="nw", image=self.tk_biche)
        else:
            self.canvas_biche.create_rectangle(0, 0, 180, 120, fill="#c8c8c8", outline="#999999")
            self.canvas_biche.create_text(90, 60, text="Biche\nImage introuvable", justify="center")

        self.label_km_biche = tk.Label(frame_left, text="—")
        self.label_km_biche.pack(pady=5)
        self.canvas_biche.bind("<Button-1>", lambda e: self.set_vehicule_actif(0))

        # Boutons (centre)
        frame_center = tk.Frame(top)
        frame_center.pack(side=tk.LEFT, expand=True)

        tk.Button(frame_center, text="Ajouter / Enregistrer", command=self.on_ajouter_plein).pack(pady=5)
        tk.Button(frame_center, text="Supprimer le plein sélectionné", command=self.on_effacer_plein).pack(pady=5)
        tk.Button(frame_center, text="Modifier le plein sélectionné", command=self.on_modifier_plein).pack(pady=5)
        tk.Button(frame_center, text="Importer un fichier (CSV)", command=self.import_csv).pack(pady=5)

        # Titine (droite)
        frame_right = tk.Frame(top)
        frame_right.pack(side=tk.RIGHT, padx=30)

        self.tk_titine, err_titine = load_photo_or_placeholder("Titine.png", (180, 120), "Titine")
        self._img_error_titine = err_titine

        self.canvas_titine = tk.Canvas(frame_right, width=180, height=120, highlightthickness=3)
        self.canvas_titine.pack()
        if self.tk_titine is not None:
            self.canvas_titine.create_image(0, 0, anchor="nw", image=self.tk_titine)
        else:
            self.canvas_titine.create_rectangle(0, 0, 180, 120, fill="#c8c8c8", outline="#999999")
            self.canvas_titine.create_text(90, 60, text="Titine\nImage introuvable", justify="center")

        self.label_km_titine = tk.Label(frame_right, text="—")
        self.label_km_titine.pack(pady=5)
        self.canvas_titine.bind("<Button-1>", lambda e: self.set_vehicule_actif(1))

        # Si erreur image, on la conserve (utile si vous voulez l'afficher)
        # (On n'affiche pas automatiquement une erreur bloquante.)

    # ---------------------
    # Onglet Pleins - Tableau + formulaire bas
    # ---------------------

    def create_main_area(self):
        frame = tk.Frame(self.tab_pleins)
        frame.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ("id", "date", "km", "litres", "prix", "total", "lieu", "type_usage", "commentaire")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")

        widths = {
            "id": 50,
            "date": 90,
            "km": 80,
            "litres": 120,
            "prix": 90,
            "total": 90,
            "lieu": 140,
            "type_usage": 160,
            "commentaire": 300,
        }

        headings = {
            "id": "ID",
            "date": "Date",
            "km": "Km",
            "litres": "Nbre de Litres",
            "prix": "€ / Litre",
            "total": "Total (€)",
            "lieu": "Lieu",
            "type_usage": "Type de Trajets",
            "commentaire": "Commentaire",
        }

        for col in columns:
            self.tree.heading(col, text=headings.get(col, col))
            self.tree.column(col, width=widths[col], stretch=(col == "commentaire"))

        self.tree.pack(fill=tk.BOTH, expand=True)

        # Formulaire en bas (comme la version précédente)
        form = tk.Frame(self.tab_pleins)
        form.pack(fill=tk.X, padx=10, pady=10)

        labels = [
            ("Jour", "jour"),
            ("Mois", "mois"),
            ("Année", "année"),
            ("Km", "kilometrage"),
            ("Nbre de Litres", "litres"),
            ("€ / Litre", "prix_litre"),
            ("Lieu", "lieu"),
            ("Type de Trajets", "type_usage"),
            ("Commentaire", "commentaire"),
        ]
        self.entries_plein = {}

        for i, (label_text, key) in enumerate(labels):
            if key == "prix_litre":
                tk.Label(form, text=label_text, font=("Arial", 12, "bold")).grid(row=0, column=i)
            else:
                tk.Label(form, text=label_text).grid(row=0, column=i)

            if key in ["jour", "mois", "année"]:
                entry = tk.Entry(form, width=6)
                entry.grid(row=1, column=i)
                self.entries_plein[key] = entry

            elif key == "lieu":
                self.combo_lieu = ttk.Combobox(form, width=16, state="readonly")
                self.combo_lieu.grid(row=1, column=i)
                self.entries_plein[key] = self.combo_lieu

            elif key == "type_usage":
                self.combo_usage = ttk.Combobox(
                    form,
                    width=18,
                    state="readonly",
                    values=["Trajets Quotidiens", "Longs Trajets"],
                )
                self.combo_usage.grid(row=1, column=i)
                self.entries_plein[key] = self.combo_usage

            else:
                entry = tk.Entry(form, width=18 if key == "commentaire" else 12)
                entry.grid(row=1, column=i)
                self.entries_plein[key] = entry

        self.refresh_pleins()
        self.refresh_kilometrages()

    def refresh_pleins(self):
        for r in self.tree.get_children():
            self.tree.delete(r)

        rows = lister_pleins(self.vehicule_actif)

        for row in rows:
            (plein_id, date_iso, km, litres, prix, total, lieu, type_usage, commentaire) = row

            try:
                an, mois, jour = date_iso.split("-")
                date_aff = f"{jour}/{mois}/{an[2:]}"
            except Exception:
                date_aff = date_iso

            self.tree.insert(
                "",
                "end",
                values=(
                    plein_id,
                    date_aff,
                    km,
                    f"{litres:.2f}",
                    f"{prix:.3f}",
                    f"{total:.2f}",
                    lieu or "",
                    type_usage or "",
                    commentaire or "",
                ),
            )

    def refresh_kilometrages(self):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("SELECT MAX(kilometrage) FROM pleins WHERE vehicule = 0")
        km_biche = cursor.fetchone()[0]
        cursor.execute("SELECT MAX(kilometrage) FROM pleins WHERE vehicule = 1")
        km_titine = cursor.fetchone()[0]

        conn.close()

        self.label_km_biche.config(text=f"{km_biche if km_biche is not None else '—'} km")
        self.label_km_titine.config(text=f"{km_titine if km_titine is not None else '—'} km")

    def refresh_lieux_ui(self):
        lieux = lister_lieux()

        self.listbox_lieux.delete(0, tk.END)
        for nom in lieux:
            self.listbox_lieux.insert(tk.END, nom)

        # Met à jour la combo dans l'onglet pleins
        if hasattr(self, "combo_lieu"):
            current = self.combo_lieu.get()
            self.combo_lieu["values"] = lieux
            self.combo_lieu.set(current if current in lieux else "")

    def set_vehicule_actif(self, index: int):
        self.vehicule_actif = index
        self.canvas_biche.config(highlightbackground="red" if index == 0 else "gray")
        self.canvas_titine.config(highlightbackground="red" if index == 1 else "gray")
        self.refresh_pleins()

    # ---------------------
    # Actions Pleins
    # ---------------------

    def on_ajouter_plein(self):
        try:
            j = int((self.entries_plein["jour"].get() or "0").strip())
            m = int((self.entries_plein["mois"].get() or "0").strip())
            a = int((self.entries_plein["année"].get() or "0").strip())

            if not (1 <= j <= 31 and 1 <= m <= 12 and 0 <= a <= 99):
                raise ValueError("Date invalide : Jour 1-31, Mois 1-12, Année sur 2 chiffres.")

            date_iso = f"20{a:02d}-{m:02d}-{j:02d}"

            km = int(self.entries_plein["kilometrage"].get())

            # Contrôle kilométrage: refuse une entrée inférieure au dernier relevé
            last_km = dernier_kilometrage(self.vehicule_actif, exclude_id=self.plein_en_cours)
            if last_km is not None and km < last_km:
                raise ValueError(f"Kilométrage incohérent : {km} km < dernier relevé ({last_km} km).")

            litres = float(self.entries_plein["litres"].get().replace(",", "."))
            prix = float(self.entries_plein["prix_litre"].get().replace(",", "."))
            total = litres * prix

            lieu = (self.entries_plein["lieu"].get() or "").strip()
            type_usage = (self.entries_plein["type_usage"].get() or "").strip()
            commentaire = (self.entries_plein["commentaire"].get() or "").strip()

            if self.plein_en_cours is not None:
                modifier_plein(
                    self.plein_en_cours,
                    self.vehicule_actif,
                    date_iso,
                    km,
                    litres,
                    prix,
                    total,
                    lieu,
                    type_usage,
                    commentaire,
                )
                self.plein_en_cours = None
            else:
                ajouter_plein(self.vehicule_actif, date_iso, km, litres, prix, total, lieu, type_usage, commentaire)

            self.refresh_pleins()
            self.refresh_kilometrages()

            # Clear fields
            for key, widget in self.entries_plein.items():
                if isinstance(widget, ttk.Combobox):
                    widget.set("")
                else:
                    widget.delete(0, tk.END)

        except Exception as e:
            messagebox.showerror("Erreur", str(e))

    def on_effacer_plein(self):
        sel = self.tree.selection()
        if not sel:
            return
        plein_id = self.tree.item(sel, "values")[0]
        supprimer_plein(plein_id)
        self.refresh_pleins()
        self.refresh_kilometrages()

    def on_modifier_plein(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Sélection", "Veuillez sélectionner un plein à modifier.")
            return

        values = self.tree.item(sel, "values")
        plein_id = values[0]

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

        # Pré-remplissage
        self.entries_plein["jour"].delete(0, tk.END)
        self.entries_plein["jour"].insert(0, jour)

        self.entries_plein["mois"].delete(0, tk.END)
        self.entries_plein["mois"].insert(0, mois)

        self.entries_plein["année"].delete(0, tk.END)
        self.entries_plein["année"].insert(0, an)

        self.entries_plein["kilometrage"].delete(0, tk.END)
        self.entries_plein["kilometrage"].insert(0, values[2])

        self.entries_plein["litres"].delete(0, tk.END)
        self.entries_plein["litres"].insert(0, values[3])

        self.entries_plein["prix_litre"].delete(0, tk.END)
        self.entries_plein["prix_litre"].insert(0, values[4])

        self.entries_plein["lieu"].set(values[6])
        self.entries_plein["type_usage"].set(values[7])

        self.entries_plein["commentaire"].delete(0, tk.END)
        self.entries_plein["commentaire"].insert(0, values[8])

        self.plein_en_cours = plein_id

    def import_csv(self):
        messagebox.showinfo("Importer CSV", "Fonction à venir.")

    # ---------------------
    # Onglet Lieux
    # ---------------------

    def create_lieux_tab(self):
        container = tk.Frame(self.tab_lieux)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        col_list = tk.Frame(container)
        col_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        col_actions = tk.Frame(container)
        col_actions.pack(side=tk.LEFT, padx=30, fill=tk.Y)

        tk.Label(col_list, text="Liste des lieux :").pack(anchor="w")
        self.listbox_lieux = tk.Listbox(col_list, height=22)
        self.listbox_lieux.pack(fill=tk.BOTH, expand=True, pady=5)

        tk.Button(col_actions, text="Ajouter un lieu…", command=self.on_ajouter_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col_actions, text="Supprimer le lieu sélectionné", command=self.on_supprimer_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col_actions, text="Renommer le lieu sélectionné…", command=self.on_renommer_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col_actions, text="Rafraîchir", command=self.refresh_lieux_ui).pack(fill=tk.X, pady=15)

        aide_texte = (
            "ℹ  Aide\n\n"
            "➕  Ajoutez un lieu pour le réutiliser dans les Pleins.\n\n"
            "🗑  La suppression est bloquée si le lieu est déjà utilisé\n"
            "     dans des pleins.\n\n"
            "✏️  Pour corriger une faute d’orthographe, utilisez « Renommer… » :\n"
            "     cela mettra à jour les pleins existants."
        )
        tk.Label(col_actions, text=aide_texte, justify="left").pack(anchor="w", pady=10)

    def on_ajouter_lieu(self):
        nom = simpledialog.askstring("Ajouter un lieu", "Nom du lieu :")
        if not nom:
            return
        ajouter_lieu(nom)
        self.refresh_lieux_ui()

    def on_supprimer_lieu(self):
        sel = self.listbox_lieux.curselection()
        if not sel:
            return
        nom = self.listbox_lieux.get(sel[0])

        n = compter_pleins_pour_lieu(nom)
        if n > 0:
            messagebox.showwarning(
                "Suppression impossible",
                f"Le lieu '{nom}' est utilisé dans {n} plein(s).\n\n"
                "Pour corriger une faute d’orthographe, utilisez plutôt « Renommer… ».",
            )
            return

        if not messagebox.askyesno("Confirmation", f"Supprimer '{nom}' ?"):
            return
        supprimer_lieu(nom)
        self.refresh_lieux_ui()

    def on_renommer_lieu(self):
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
            renommer_lieu(ancien, nouveau)
        except Exception as e:
            messagebox.showerror("Erreur", str(e))
            return
        self.refresh_lieux_ui()


if __name__ == "__main__":
    app = GarageApp()
    app.mainloop()
