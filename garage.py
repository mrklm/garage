import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import sqlite3
from PIL import Image, ImageTk

DB_FILE = "garage.db"

# =========================
# Base de données (SQLite)
# =========================

def init_db():
    """Initialise la base (tables + lieux par défaut)."""
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

    # Lieux par défaut (sans doublons)
    cursor.execute(
        """
        INSERT OR IGNORE INTO lieux (nom) VALUES
        ('St É'),
        ('Avranches'),
        ('Pontorson'),
        ('Pleine Fougères'),
        ('Lille')
        """
    )

    conn.commit()
    conn.close()


def ajouter_plein(vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO pleins
        (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
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
    """Plus récent en haut."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire
        FROM pleins
        WHERE vehicule = ?
        ORDER BY date DESC, id DESC
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


def dernier_kilometrage(vehicule):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(kilometrage) FROM pleins WHERE vehicule = ?", (vehicule,))
    result = cursor.fetchone()[0]
    conn.close()
    return result


def lister_lieux():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT nom FROM lieux ORDER BY nom")
    rows = [r[0] for r in cursor.fetchall()]
    conn.close()
    return rows


def ajouter_lieu(nom: str):
    nom = (nom or "").strip()
    if not nom:
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO lieux (nom) VALUES (?)", (nom,))
    conn.commit()
    conn.close()


def supprimer_lieu(nom: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM lieux WHERE nom = ?", (nom,))
    conn.commit()
    conn.close()


def lieux_frequents_non_catalogues(min_occurrences: int = 3):
    """Suggestions: lieux fréquents présents dans pleins mais absents de la table lieux."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT t.nom, t.n
        FROM (
            SELECT TRIM(lieu) AS nom, COUNT(*) AS n
            FROM pleins
            WHERE lieu IS NOT NULL
              AND TRIM(lieu) <> ''
            GROUP BY TRIM(lieu)
        ) AS t
        WHERE t.n >= ?
          AND t.nom NOT IN (SELECT nom FROM lieux)
        ORDER BY t.n DESC, t.nom ASC
        """,
        (min_occurrences,),
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


# =========================
# Interface graphique
# =========================

class GarageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Garage – gestion des véhicules")
        self.geometry("1100x650")

        init_db()

        self.vehicule_actif = 0
        self.plein_en_cours = None

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_pleins = tk.Frame(self.notebook)
        self.tab_lieux = tk.Frame(self.notebook)

        self.notebook.add(self.tab_pleins, text="Pleins")
        self.notebook.add(self.tab_lieux, text="Lieux")

        self.create_top_bar()
        self.create_main_area()
        self.create_lieux_tab()

        self.refresh_lieux_ui()
        self.set_vehicule_actif(0)

    # ---------------------
    # Onglet Pleins
    # ---------------------

    def create_top_bar(self):
        top = tk.Frame(self.tab_pleins)
        top.pack(fill=tk.X, pady=10)

        # Biche (gauche)
        frame_left = tk.Frame(top)
        frame_left.pack(side=tk.LEFT, padx=30)

        self.img_biche = Image.open("Biche.png").resize((180, 120))
        self.tk_biche = ImageTk.PhotoImage(self.img_biche)

        self.canvas_biche = tk.Canvas(frame_left, width=180, height=120, highlightthickness=3)
        self.canvas_biche.pack()
        self.canvas_biche.create_image(0, 0, anchor="nw", image=self.tk_biche)

        self.label_km_biche = tk.Label(frame_left, text="—")
        self.label_km_biche.pack(pady=5)

        self.canvas_biche.bind("<Button-1>", lambda e: self.set_vehicule_actif(0))

        # Actions (centre)
        frame_center = tk.Frame(top)
        frame_center.pack(side=tk.LEFT, expand=True)

        tk.Button(frame_center, text="Ajouter / Enregistrer", command=self.on_ajouter_plein).pack(pady=5)
        tk.Button(frame_center, text="Supprimer le plein sélectionné", command=self.on_effacer_plein).pack(pady=5)
        tk.Button(frame_center, text="Modifier le plein sélectionné", command=self.on_modifier_plein).pack(pady=5)
        tk.Button(frame_center, text="Importer un fichier", command=self.import_csv).pack(pady=5)

        # Titine (droite)
        frame_right = tk.Frame(top)
        frame_right.pack(side=tk.RIGHT, padx=30)

        self.img_titine = Image.open("Titine.png").resize((180, 120))
        self.tk_titine = ImageTk.PhotoImage(self.img_titine)

        self.canvas_titine = tk.Canvas(frame_right, width=180, height=120, highlightthickness=3)
        self.canvas_titine.pack()
        self.canvas_titine.create_image(0, 0, anchor="nw", image=self.tk_titine)

        self.label_km_titine = tk.Label(frame_right, text="—")
        self.label_km_titine.pack(pady=5)

        self.canvas_titine.bind("<Button-1>", lambda e: self.set_vehicule_actif(1))

    def create_main_area(self):
        frame = tk.Frame(self.tab_pleins)
        frame.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ("id", "date", "km", "litres", "prix", "total", "lieu", "usage", "commentaire")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")

        widths = {
            "id": 50,
            "date": 90,
            "km": 90,
            "litres": 70,
            "prix": 80,
            "total": 80,
            "lieu": 130,
            "usage": 120,
            "commentaire": 260,
        }

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], stretch=False)

        self.tree.pack(fill=tk.BOTH, expand=True)

        form = tk.Frame(self.tab_pleins)
        form.pack(fill=tk.X, pady=5)

        labels = ["Jour", "Mois", "Année", "kilometrage", "litres", "prix_litre", "lieu", "type_usage", "commentaire"]
        self.entries_plein = {}

        for i, lab in enumerate(labels):
            tk.Label(form, text=lab).grid(row=0, column=i)

            if lab in ["Jour", "Mois", "Année"]:
                entry = tk.Entry(form, width=6)
                entry.grid(row=1, column=i)
                self.entries_plein[lab.lower()] = entry

            elif lab == "lieu":
                self.combo_lieu = ttk.Combobox(form, width=16, state="readonly")
                self.combo_lieu.grid(row=1, column=i)
                self.entries_plein["lieu"] = self.combo_lieu

            else:
                entry = tk.Entry(form, width=12)
                entry.grid(row=1, column=i)
                self.entries_plein[lab.lower()] = entry

    # ---------------------
    # Onglet Lieux
    # ---------------------

    def create_lieux_tab(self):
        container = tk.Frame(self.tab_lieux)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        col1 = tk.Frame(container)
        col1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(col1, text="Lieux enregistrés").pack(anchor="w")
        self.listbox_lieux = tk.Listbox(col1, height=18, width=40)
        self.listbox_lieux.pack(fill=tk.BOTH, expand=True, pady=8)

        col2 = tk.Frame(container)
        col2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(20, 0))

        tk.Label(col2, text="Suggestions (≥ 3 pleins)\nissus des données").pack(anchor="w")
        self.listbox_suggestions = tk.Listbox(col2, height=18, width=45)
        self.listbox_suggestions.pack(fill=tk.BOTH, expand=True, pady=8)

        col3 = tk.Frame(container)
        col3.pack(side=tk.LEFT, padx=20, fill=tk.Y)

        tk.Button(col3, text="Ajouter un lieu…", command=self.on_ajouter_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col3, text="Ajouter la suggestion sélectionnée", command=self.on_ajouter_suggestion).pack(fill=tk.X, pady=5)
        tk.Button(col3, text="Supprimer le lieu sélectionné", command=self.on_supprimer_lieu).pack(fill=tk.X, pady=5)
        tk.Button(col3, text="Rafraîchir", command=self.refresh_lieux_ui).pack(fill=tk.X, pady=15)

        tk.Label(
            col3,
            text=(
                "Astuce :\n"
                "- Les suggestions viennent des pleins\n"
                "  déjà saisis (champ 'lieu')\n"
                "- Quand tu ajoutes une suggestion,\n"
                "  elle devient disponible dans\n"
                "  la liste déroulante des Pleins"
            ),
            justify="left",
        ).pack(anchor="w", pady=10)

    # ---------------------
    # Rafraîchissements
    # ---------------------

    def refresh_lieux_ui(self):
        lieux = lister_lieux()

        self.listbox_lieux.delete(0, tk.END)
        for nom in lieux:
            self.listbox_lieux.insert(tk.END, nom)

        self.listbox_suggestions.delete(0, tk.END)
        for nom, n in lieux_frequents_non_catalogues(3):
            self.listbox_suggestions.insert(tk.END, f"{nom}  (×{n})")

        current = self.combo_lieu.get() if hasattr(self, "combo_lieu") else ""
        if hasattr(self, "combo_lieu"):
            self.combo_lieu["values"] = lieux
            self.combo_lieu.set(current if current in lieux else "")

    def set_vehicule_actif(self, index: int):
        self.vehicule_actif = index
        self.canvas_biche.config(highlightbackground="red" if index == 0 else "gray")
        self.canvas_titine.config(highlightbackground="red" if index == 1 else "gray")
        self.refresh_pleins()
        self.refresh_kilometrages()

    def refresh_pleins(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in lister_pleins(self.vehicule_actif):
            row = list(row)
            date_val = row[1]
            if date_val:
                try:
                    if "-" in date_val:
                        an, mois, jour = date_val.split("-")
                        row[1] = f"{jour}/{mois}/{an[2:]}"
                except Exception:
                    pass

            self.tree.insert("", tk.END, values=row)

    def refresh_kilometrages(self):
        kb = dernier_kilometrage(0)
        kt = dernier_kilometrage(1)
        self.label_km_biche.config(text=f"{kb:,} Km".replace(",", " ") if kb is not None else "—")
        self.label_km_titine.config(text=f"{kt:,} Km".replace(",", " ") if kt is not None else "—")

    # ---------------------
    # Actions Pleins
    # ---------------------

    def on_ajouter_plein(self):
        try:
            j = int((self.entries_plein["jour"].get() or "0").strip())
            m = int((self.entries_plein["mois"].get() or "0").strip())
            a = int((self.entries_plein["année"].get() or "0").strip())

            if not (1 <= j <= 31 and 1 <= m <= 12 and 0 <= a <= 99):
                raise ValueError("Date invalide : Jour 1-31, Mois 1-12, Année sur 2 chiffres")

            date_iso = f"20{a:02d}-{m:02d}-{j:02d}"

            km = int(self.entries_plein["kilometrage"].get())
            litres = float(self.entries_plein["litres"].get().replace(",", "."))
            prix = float(self.entries_plein["prix_litre"].get().replace(",", "."))
            total = litres * prix

            lieu = (self.combo_lieu.get() or "").strip() if hasattr(self, "combo_lieu") else ""
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

            for widget in self.entries_plein.values():
                if isinstance(widget, ttk.Combobox):
                    widget.set("")
                elif isinstance(widget, tk.Entry):
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
            messagebox.showwarning("Sélection", "Veuillez sélectionner un plein à modifier")
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

        if hasattr(self, "combo_lieu"):
            self.combo_lieu.set(str(values[6]) if values[6] is not None else "")

        self.entries_plein["type_usage"].delete(0, tk.END)
        self.entries_plein["type_usage"].insert(0, values[7] if values[7] is not None else "")

        self.entries_plein["commentaire"].delete(0, tk.END)
        self.entries_plein["commentaire"].insert(0, values[8] if values[8] is not None else "")

        self.plein_en_cours = plein_id

    def import_csv(self):
        messagebox.showinfo("Info", "Import CSV à venir")

    # ---------------------
    # Actions Lieux
    # ---------------------

    def on_ajouter_lieu(self):
        nom = simpledialog.askstring("Nouveau lieu", "Nom du lieu :")
        if nom:
            ajouter_lieu(nom)
            self.refresh_lieux_ui()

    def on_supprimer_lieu(self):
        sel = self.listbox_lieux.curselection()
        if not sel:
            return
        nom = self.listbox_lieux.get(sel[0])
        if not messagebox.askyesno("Confirmation", f"Supprimer '{nom}' ?"):
            return
        supprimer_lieu(nom)
        self.refresh_lieux_ui()

    def on_ajouter_suggestion(self):
        sel = self.listbox_suggestions.curselection()
        if not sel:
            messagebox.showwarning("Sélection", "Sélectionne une suggestion à ajouter")
            return

        raw = self.listbox_suggestions.get(sel[0])
        nom = raw.split("(×", 1)[0].strip()
        if not nom:
            return

        ajouter_lieu(nom)
        self.refresh_lieux_ui()


if __name__ == "__main__":
    app = GarageApp()
    app.mainloop()
