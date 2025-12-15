import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from PIL import Image, ImageTk

DB_FILE = "garage.db"

# =========================
# Base de données
# =========================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pleins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vehicule INTEGER,
            date TEXT,
            kilometrage INTEGER,
            litres REAL,
            prix_litre REAL,
            total REAL,
            lieu TEXT,
            type_usage TEXT,
            commentaire TEXT
        )
    """)
    conn.commit()
    conn.close()


def ajouter_plein(vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO pleins
        (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire))
    conn.commit()
    conn.close()


def lister_pleins(vehicule):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire
        FROM pleins
        WHERE vehicule = ?
        ORDER BY date
    """, (vehicule,))
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
    cursor.execute("""
        SELECT MAX(kilometrage)
        FROM pleins
        WHERE vehicule = ?
    """, (vehicule,))
    result = cursor.fetchone()[0]
    conn.close()
    return result


# =========================
# Interface graphique
# =========================

class GarageApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Garage – gestion des véhicules")
        self.geometry("1000x600")

        self.vehicule_actif = 0

        init_db()

        self.create_top_bar()
        self.create_main_area()

        self.refresh_pleins()
        self.refresh_kilometrages()
        self.set_vehicule_actif(0)

    # =====================
    # BARRE HAUTE
    # =====================

    def create_top_bar(self):
        top = tk.Frame(self)
        top.pack(fill=tk.X, pady=10)

        # ---- GAUCHE : BICHE ----
        frame_left = tk.Frame(top)
        frame_left.pack(side=tk.LEFT, padx=30)

        self.img_biche = Image.open("Biche.png").resize((180, 120))
        self.tk_biche = ImageTk.PhotoImage(self.img_biche)

        self.canvas_biche = tk.Canvas(
            frame_left, width=180, height=120, highlightthickness=3
        )
        self.canvas_biche.pack()
        self.canvas_biche.create_image(0, 0, anchor="nw", image=self.tk_biche)

        self.label_km_biche = tk.Label(frame_left, text="—")
        self.label_km_biche.pack(pady=5)

        self.canvas_biche.bind("<Button-1>", lambda e: self.set_vehicule_actif(0))

        # ---- CENTRE : ACTIONS ----
        frame_center = tk.Frame(top)
        frame_center.pack(side=tk.LEFT, expand=True)

        tk.Button(frame_center, text="Ajouter un plein",
                  command=self.on_ajouter_plein).pack(pady=5)

        tk.Button(frame_center, text="Importer un fichier",
                  command=self.import_csv).pack(pady=5)

        tk.Button(frame_center, text="Supprimer le plein sélectionné",
                  command=self.on_effacer_plein).pack(pady=5)

        # ---- DROITE : TITINE ----
        frame_right = tk.Frame(top)
        frame_right.pack(side=tk.RIGHT, padx=30)

        self.img_titine = Image.open("Titine.png").resize((180, 120))
        self.tk_titine = ImageTk.PhotoImage(self.img_titine)

        self.canvas_titine = tk.Canvas(
            frame_right, width=180, height=120, highlightthickness=3
        )
        self.canvas_titine.pack()
        self.canvas_titine.create_image(0, 0, anchor="nw", image=self.tk_titine)

        self.label_km_titine = tk.Label(frame_right, text="—")
        self.label_km_titine.pack(pady=5)

        self.canvas_titine.bind("<Button-1>", lambda e: self.set_vehicule_actif(1))

    # =====================
    # ZONE PRINCIPALE
    # =====================

    def create_main_area(self):
        frame = tk.Frame(self)
        frame.pack(fill=tk.BOTH, expand=True, padx=10)

        columns = ("id", "date", "km", "litres", "prix", "total", "lieu", "usage", "commentaire")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")

        widths = {
            "id": 40, "date": 80, "km": 80, "litres": 70,
            "prix": 80, "total": 80, "lieu": 100,
            "usage": 100, "commentaire": 200
        }

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=widths[col], stretch=False)

        self.tree.pack(fill=tk.BOTH, expand=True)

        # ---- FORMULAIRE ----
        form = tk.Frame(self)
        form.pack(fill=tk.X, pady=5)

        labels = ["date", "kilometrage", "litres", "prix_litre", "lieu", "type_usage", "commentaire"]
        self.entries_plein = {}

        for i, lab in enumerate(labels):
            tk.Label(form, text=lab).grid(row=0, column=i)
            e = tk.Entry(form, width=12)
            e.grid(row=1, column=i)
            self.entries_plein[lab] = e

        self.entries_plein["date"].insert(0, "JJ/MM/AA")

    # =====================
    # LOGIQUE
    # =====================

    def set_vehicule_actif(self, index):
        self.vehicule_actif = index

        self.canvas_biche.config(
            highlightbackground="red" if index == 0 else "gray"
        )
        self.canvas_titine.config(
            highlightbackground="red" if index == 1 else "gray"
        )

        self.refresh_pleins()

    def refresh_kilometrages(self):
        kb = dernier_kilometrage(0)
        kt = dernier_kilometrage(1)

        self.label_km_biche.config(
            text=f"{kb:,} Km".replace(",", " ") if kb else "—"
        )
        self.label_km_titine.config(
            text=f"{kt:,} Km".replace(",", " ") if kt else "—"
        )


    def refresh_pleins(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        for row in lister_pleins(self.vehicule_actif):
            row = list(row)

            # date ISO → JJ/MM/AA
            an, mois, jour = row[1].split("-")
            row[1] = f"{jour}/{mois}/{an[2:]}"

            self.tree.insert("", tk.END, values=row)

    def on_ajouter_plein(self):
        try:
            d = self.entries_plein["date"].get()
            parts = d.split("/")
            if len(parts) != 3:
                raise ValueError("Date invalide : utilisez le format JJ/MM/AA")
            j, m, a = parts
            date_iso = f"20{a}-{m}-{j}"  # conversion en YYYY-MM-DD

            km = int(self.entries_plein["kilometrage"].get())
            litres = float(self.entries_plein["litres"].get().replace(",", "."))
            prix = float(self.entries_plein["prix_litre"].get().replace(",", "."))
            total = litres * prix

            ajouter_plein(
                self.vehicule_actif,
                date_iso,
                km,
                litres,
                prix,
                total,
                self.entries_plein["lieu"].get(),
                self.entries_plein["type_usage"].get(),
                self.entries_plein["commentaire"].get()
            )

            self.refresh_pleins()
            self.refresh_kilometrages()

            for e in self.entries_plein.values():
                e.delete(0, tk.END)

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

    def import_csv(self):
        messagebox.showinfo("Info", "Import CSV à venir")


# =========================
# Lancement
# =========================

if __name__ == "__main__":
    app = GarageApp()
    app.mainloop()
