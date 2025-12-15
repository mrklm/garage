import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import sqlite3
from PIL import Image, ImageTk

DB_FILE = "garage.db"

# --- Fonctions base de données ---
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
        INSERT INTO pleins (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire))
    conn.commit()
    conn.close()

def lister_pleins(vehicule):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire
        FROM pleins WHERE vehicule=?
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

# --- Application Tkinter ---
class GarageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestion Garage")
        self.geometry("800x500")
        self.vehicule_actif = 0  # 0=Biche, 1=Titine
        init_db()
        self.create_top_bar()
        self.create_main_area()
        self.refresh_pleins()

    # --- Barre du haut ---
    def create_top_bar(self):
        top_frame = tk.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)

        # Boutons à gauche
        frame_buttons = tk.Frame(top_frame)
        frame_buttons.pack(side=tk.LEFT, padx=10)
        btn_add_vehicle = tk.Button(frame_buttons, text="Ajouter un véhicule")
        btn_add_vehicle.pack(pady=5)
        btn_add_file = tk.Button(frame_buttons, text="Ajouter un fichier de plein")
        btn_add_file.pack(pady=5)

        # Images à droite
        frame_images = tk.Frame(top_frame)
        frame_images.pack(side=tk.RIGHT, padx=10)
        self.img_biche = Image.open("Biche.png").resize((150, 100))
        self.img_titine = Image.open("Titine.png").resize((150, 100))
        self.tk_biche = ImageTk.PhotoImage(self.img_biche)
        self.tk_titine = ImageTk.PhotoImage(self.img_titine)
        self.canvas = tk.Canvas(frame_images, width=320, height=120)
        self.canvas.pack()
        self.image_biche_id = self.canvas.create_image(0, 0, anchor='nw', image=self.tk_biche)
        self.image_titine_id = self.canvas.create_image(160, 0, anchor='nw', image=self.tk_titine)
        self.rectangle_id = self.canvas.create_rectangle(
            0, 0, self.img_biche.width, self.img_biche.height, outline="red", width=3
        )

        # Rendre les images cliquables
        self.canvas.tag_bind(self.image_biche_id, "<Button-1>", lambda e: self.set_vehicule_actif(0))
        self.canvas.tag_bind(self.image_titine_id, "<Button-1>", lambda e: self.set_vehicule_actif(1))

    def set_vehicule_actif(self, index):
        self.vehicule_actif = index
        if index == 0:
            self.canvas.coords(self.rectangle_id, 0, 0, self.img_biche.width, self.img_biche.height)
        else:
            self.canvas.coords(self.rectangle_id, 160, 0, 160 + self.img_titine.width, self.img_titine.height)
        self.refresh_pleins()

    # --- Zone principale ---
    def create_main_area(self):
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Treeview pour les pleins
        columns = ("id","date","km","litres","prix_litre","total","lieu","type_usage","commentaire")
        self.tree_pleins = ttk.Treeview(main_frame, columns=columns, show="headings")
        for col in columns:
            self.tree_pleins.heading(col, text=col)
        self.tree_pleins.pack(fill=tk.BOTH, expand=True)

        # Formulaire d'ajout
        form_frame = tk.Frame(main_frame)
        form_frame.pack(fill=tk.X, pady=5)
        labels = ["date","kilometrage","litres","prix_litre","lieu","type_usage","commentaire"]
        self.entries_plein = {}
        for i, label in enumerate(labels):
            tk.Label(form_frame, text=label).grid(row=0, column=i)
            e = tk.Entry(form_frame, width=10)
            e.grid(row=1, column=i)
            self.entries_plein[label] = e

        # Boutons ajouter / effacer
        btn_frame = tk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=5)
        tk.Button(btn_frame, text="Ajouter plein", command=self.on_ajouter_plein).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Effacer plein", command=self.on_effacer_plein).pack(side=tk.LEFT, padx=5)

    # --- Ajouter plein ---
    def on_ajouter_plein(self):
        try:
            date = self.entries_plein["date"].get()
            kilometrage = int(self.entries_plein["kilometrage"].get())
            litres = float(self.entries_plein["litres"].get().replace(',', '.'))
            prix_litre = float(self.entries_plein["prix_litre"].get().replace(',', '.'))
            total = litres * prix_litre
            lieu = self.entries_plein["lieu"].get()
            type_usage = self.entries_plein["type_usage"].get()
            commentaire = self.entries_plein["commentaire"].get()
            ajouter_plein(self.vehicule_actif, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
            self.refresh_pleins()
            for e in self.entries_plein.values():
                e.delete(0, tk.END)
        except ValueError:
            messagebox.showerror("Erreur", "Veuillez entrer des valeurs numériques valides pour kilométrage, litres et prix_litre.")

    # --- Effacer plein sélectionné ---
    def on_effacer_plein(self):
        selected_item = self.tree_pleins.selection()
        if not selected_item:
            return
        plein_id = self.tree_pleins.item(selected_item, "values")[0]
        supprimer_plein(plein_id)
        self.refresh_pleins()

    # --- Rafraîchir la liste ---
    def refresh_pleins(self):
        for row in self.tree_pleins.get_children():
            self.tree_pleins.delete(row)
        for row in lister_pleins(self.vehicule_actif):
        row = list(row)

        # Conversion date YYYY-MM-DD → JJ/MM/AA
        if row[1]:
            an, mois, jour = row[1].split("-")
            row[1] = f"{jour}/{mois}/{an[2:]}"

        self.tree_pleins.insert("", tk.END, values=row)


if __name__ == "__main__":
    app = GarageApp()
    app.mainloop()
