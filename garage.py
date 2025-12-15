import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv

DB_NAME = "garage.db"

# ---------------------------
# Base de données
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Table véhicules
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS vehicule (
            id_vehicule INTEGER PRIMARY KEY AUTOINCREMENT,
            nom TEXT NOT NULL,
            marque TEXT,
            modele TEXT,
            annee INTEGER,
            motorisation TEXT,
            commentaire TEXT
        )
    """)
    # Table pleins carburant
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plein_carburant (
            id_plein INTEGER PRIMARY KEY AUTOINCREMENT,
            id_vehicule INTEGER,
            date TEXT,
            kilometrage INTEGER,
            litres REAL,
            prix_litre REAL,
            total REAL,
            lieu TEXT,
            type_usage TEXT,
            commentaire TEXT,
            FOREIGN KEY (id_vehicule) REFERENCES vehicule(id_vehicule)
        )
    """)
    # Table entretiens
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS entretien (
            id_entretien INTEGER PRIMARY KEY AUTOINCREMENT,
            id_vehicule INTEGER,
            date TEXT,
            kilometrage INTEGER,
            type_entretien TEXT,
            description TEXT,
            cout REAL,
            commentaire TEXT,
            FOREIGN KEY (id_vehicule) REFERENCES vehicule(id_vehicule)
        )
    """)
    conn.commit()
    conn.close()

# ---------------------------
# Fonctions base
# ---------------------------
def ajouter_vehicule(nom, marque, modele, annee, motorisation, commentaire):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO vehicule (nom, marque, modele, annee, motorisation, commentaire)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (nom, marque, modele, annee, motorisation, commentaire))
    conn.commit()
    conn.close()

def lister_vehicules():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id_vehicule, nom, marque, modele, annee, motorisation FROM vehicule ORDER BY nom")
    rows = cursor.fetchall()
    conn.close()
    return rows

def dernier_kilometrage(id_vehicule):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT kilometrage FROM plein_carburant
        WHERE id_vehicule = ?
        ORDER BY date DESC, id_plein DESC
        LIMIT 1
    """, (id_vehicule,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def ajouter_plein(id_vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO plein_carburant
        (id_vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (id_vehicule, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire))
    conn.commit()
    conn.close()

def lister_pleins(id_vehicule):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire
        FROM plein_carburant
        WHERE id_vehicule = ?
        ORDER BY date
    """, (id_vehicule,))
    rows = cursor.fetchall()
    conn.close()
    return rows

# ---------------------------
# Interface Tkinter
# ---------------------------
class GarageApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Gestion du garage du ménage")
        self.geometry("850x650")
        self.resizable(True, True)
        self.vehicule_actif = None
        self.create_widgets()
        self.refresh_vehicules()

    def create_widgets(self):
        # Boutons ajout véhicule et import
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=5)
        ttk.Button(btn_frame, text="Ajouter un véhicule", command=self.ajout_vehicule_popup).pack(side="left")
        ttk.Button(btn_frame, text="Importer un fichier de plein", command=self.importer_csv).pack(side="left", padx=5)

        # Liste véhicules simplifiée
        self.tree_vehicules = ttk.Treeview(self, columns=("nom", "dernier_km"), show="headings", height=2)
        self.tree_vehicules.heading("nom", text="Véhicule")
        self.tree_vehicules.heading("dernier_km", text="Dernier kilométrage")
        self.tree_vehicules.pack(fill="x", padx=10, pady=5)
        self.tree_vehicules.bind("<<TreeviewSelect>>", self.on_select_vehicule)

        # Formulaire plein carburant
        self.form_plein = ttk.LabelFrame(self, text="Ajouter un plein de carburant", padding=10)
        self.form_plein.pack(fill="x", padx=10, pady=5)
        self.entries_plein = {}
        champs_plein = [("Date (YYYY-MM-DD)", "date"), ("Kilométrage", "kilometrage"), ("Litres", "litres"),
                        ("Prix litre", "prix_litre"), ("Lieu", "lieu"), ("Type usage", "type_usage"), ("Commentaire", "commentaire")]
        for i, (label, key) in enumerate(champs_plein):
            ttk.Label(self.form_plein, text=label).grid(row=i, column=0, sticky="w", pady=2)
            entry = ttk.Entry(self.form_plein)
            entry.grid(row=i, column=1, sticky="ew", pady=2)
            self.entries_plein[key] = entry
        self.form_plein.columnconfigure(1, weight=1)
        ttk.Button(self.form_plein, text="Ajouter plein", command=self.on_ajouter_plein).grid(row=len(champs_plein), column=0, columnspan=2, pady=5)

        # Tableau pleins
        table_frame2 = ttk.LabelFrame(self, text="Historique pleins", padding=5)
        table_frame2.pack(fill="both", expand=True, padx=10, pady=5)
        columns2 = ("date", "kilometrage", "litres", "prix_litre", "total", "lieu", "type_usage", "commentaire")
        self.tree_pleins = ttk.Treeview(table_frame2, columns=columns2, show="headings")
        for col in columns2:
            self.tree_pleins.heading(col, text=col.capitalize())
        self.tree_pleins.pack(fill="both", expand=True)

    # -----------------------
    # Fonctions principales
    # -----------------------
    def refresh_vehicules(self):
        for item in self.tree_vehicules.get_children():
            self.tree_vehicules.delete(item)
        for row in lister_vehicules():
            veh_id, nom, *rest = row
            km = dernier_kilometrage(veh_id)
            self.tree_vehicules.insert("", "end", values=(nom, km), iid=veh_id)

    def ajout_vehicule_popup(self):
        popup = tk.Toplevel(self)
        popup.title("Ajouter un véhicule")
        labels = ["Nom*", "Marque", "Modèle", "Année", "Motorisation", "Commentaire"]
        entries = []
        for i, l in enumerate(labels):
            ttk.Label(popup, text=l).grid(row=i, column=0)
            e = ttk.Entry(popup)
            e.grid(row=i, column=1)
            entries.append(e)

        def valider():
            nom = entries[0].get().strip()
            if not nom:
                messagebox.showerror("Erreur", "Nom obligatoire")
                return
            marque = entries[1].get()
            modele = entries[2].get()
            annee = int(entries[3].get()) if entries[3].get().isdigit() else None
            motorisation = entries[4].get()
            commentaire = entries[5].get()
            ajouter_vehicule(nom, marque, modele, annee, motorisation, commentaire)
            self.refresh_vehicules()
            popup.destroy()

        ttk.Button(popup, text="Ajouter", command=valider).grid(row=len(labels), column=0, columnspan=2, pady=5)

    def on_select_vehicule(self, event):
        sel = self.tree_vehicules.selection()
        if sel:
            self.vehicule_actif = int(sel[0])
            self.refresh_pleins()

    def on_ajouter_plein(self):
        if not self.vehicule_actif:
            messagebox.showerror("Erreur", "Sélectionnez un véhicule")
            return
        date = self.entries_plein["date"].get()
        kilometrage = int(self.entries_plein["kilometrage"].get())
        litres = float(self.entries_plein["litres"].get())
        prix_litre = float(self.entries_plein["prix_litre"].get())
        total = litres * prix_litre
        lieu = self.entries_plein["lieu"].get()
        type_usage = self.entries_plein["type_usage"].get()
        commentaire = self.entries_plein["commentaire"].get()
        ajouter_plein(self.vehicule_actif, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
        self.refresh_pleins()
        self.refresh_vehicules()
        for e in self.entries_plein.values():
            e.delete(0, tk.END)

    def refresh_pleins(self):
        for item in self.tree_pleins.get_children():
            self.tree_pleins.delete(item)
        if self.vehicule_actif:
            for row in lister_pleins(self.vehicule_actif):
                self.tree_pleins.insert("", "end", values=row)

    # -----------------------
    # Import CSV
    # -----------------------
    def importer_csv(self):
        if not self.vehicule_actif:
            messagebox.showerror("Erreur", "Sélectionnez un véhicule avant d'importer")
            return
        filename = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filename:
            return
        with open(filename, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            count = 0
            for row in reader:
                try:
                    date = row['date']
                    kilometrage = int(row['kilometrage'])
                    litres = float(row['litres'])
                    prix_litre = float(row['prix_litre'])
                    total = litres * prix_litre
                    lieu = row.get('lieu', '')
                    type_usage = row.get('type_usage', '')
                    commentaire = row.get('commentaire', '')
                    ajouter_plein(self.vehicule_actif, date, kilometrage, litres, prix_litre, total, lieu, type_usage, commentaire)
                    count += 1
                except Exception as e:
                    messagebox.showwarning("Import partiel", f"Erreur sur ligne : {row}\n{e}")
            messagebox.showinfo("Import terminé", f"{count} pleins importés avec succès")
            self.refresh_pleins()
            self.refresh_vehicules()

# ---------------------------
# Lancement
# ---------------------------
if __name__ == "__main__":
    init_db()
    app = GarageApp()
    app.mainloop()
