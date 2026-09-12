# GARAGE

![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-GPLv3-blue)
![Version](https://img.shields.io/badge/version-5.0.3-green)


**Garage** est une application simple et autonome pour suivre les informations essentielles de vos véhicules.

Elle permet de gérer :

- les véhicules (type, photo, caractéristiques),
- les entretiens réalisés et à prévoir, avec leurs fréquences constructeur,
- les pleins de carburant.
- Votre budget véhicule.

L’onglet **Général** affiche automatiquement :

- les rappels d’entretien à effectuer,
- la moyenne du coût du véhicule par an, 
- la consommation moyenne (L/100 km),
- une estimation des coûts à prévoir sur les six prochains mois,
- l’état de la batterie (si renseigné).
- Des graphiques de la conso L/100km de l'évolution dans le temps des prix -entretiens /réparations /carburant.
---

## Aperçu

![Scction Aide](screenshots/aide.png)
![Fenêtre principale](screenshots/general.png)
![Fenêtre Véhicule](screenshots/vehicule.png)
![Fenêtre Pleins](screenshots/plein.png)
![Fenêtre Entretiens](screenshots/entretiens.png)
![Fenêtre Graphes](screenshots/graphes.png)

---

## 📥 Téléchargement

👉 Les versions compilées sont disponibles dans la section **Releases** :  
https://github.com/mrklm/garage/releases

### Applications standalone (recommandé)

- **Linux**  
  - `Garagev5.0.3-linux-x86_64.Appimage`
  - `Garagev5.0.3-linux-x86_64.Appimage.sha`
  - `Garage v5.0.3 linux-x86_64.tar.gz`
  - `Garage v5.0.3 linux-x86_64.tar.gz.sha`
  - `SHA256SUMS-Garage-v5.0.3.txt`

- **macOS**  
  - `Garage-5.0.3-macOS-x86_64.dmg`
  - `Garage-5.0.3-macOS-x86_64.dmg.sha`

- **Windows**  
  - `Garage-v5.0.3-windows-x86_64.zip`
  - `Garage-v5.0.3-windows-x86_64.zip.sha`

La release standard contient les builds macOS moderne, Linux et Windows.
Une version macOS High Sierra sera publiée séparément lorsqu'elle sera disponible.
Elle ne fait pas partie de la release standard.

---

## 🐧 Linux / Ubuntu

### Option 1 — AppImage (recommandé)

```bash
chmod +x Garagev5.0.3-linux-x86_64.Appimage
./Garagev5.0.3-linux-x86_64.Appimage
```

### Option 2 — Archive `.tar.gz`

```bash
tar -xzf "Garage v5.0.3 linux-x86_64.tar.gz"
cd "Garage v5.0.3 linux-x86_64"
./Garage
```

---

## 💾 Données et base de données

Garage utilise une **base de données persistante**.

Garage stocke ses données utilisateur dans le dossier Garage propre à votre système :

```text
Linux   : ~/.local/share/Garage
          ou $XDG_DATA_HOME/Garage si XDG_DATA_HOME est défini

macOS   : ~/Library/Application Support/Garage

Windows : %APPDATA%\Garage
```

La base principale est `garage.db`.
Les photos des véhicules sont stockées dans le sous-dossier `vehicle_photos`.

Lors du premier lancement, la base est automatiquement créée si elle n'existe pas.

### Sauvegarde / restauration

Garage propose une fonction intégrée dans `Paramètres > Données`.

- `Exporter une sauvegarde` crée une archive ZIP contenant les données Garage et les photos des véhicules.
- `Importer une sauvegarde` restaure les données et les photos depuis l'archive sélectionnée.
- Une sauvegarde de sécurité est créée automatiquement avant import.
- Après une restauration réussie, Garage demande un redémarrage.

---

## 🚀 Installation depuis les sources (optionnel)

### Prérequis
- Python 3.10+
- Tkinter
- SQLite, généralement fourni avec Python
- Pillow
- Matplotlib
- NumPy
- python-dateutil

### 1. Cloner le dépôt
```bash
git clone https://github.com/mrklm/garage.git
cd garage
```

### 2. Créer un environnement virtuel
```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

### 3. Lancer l’application sur macOS / Linux
```bash
python3 garage.py
```

Sous Windows, utilisez généralement :

```powershell
python garage.py
```

---

## 📜 Licence

Ce logiciel est distribué sous la **GNU General Public License v3.0**.

---

## 🛠️ Contribuer

Les contributions sont les bienvenues via *Pull Requests*.

---

## 📬 Contact

**clementmorel@free.fr**

---

✨ Bonne route avec Garage !
