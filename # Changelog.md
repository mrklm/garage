# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.  
Le format est inspiré de *Keep a Changelog* et le versionnement suit une logique sémantique pragmatique.

## [4.5.29] – 2026-09-12

### Modifié

- Mise à jour complète de l'aide utilisateur pour correspondre à la
  nouvelle organisation de Garage.
- Documentation de la navigation principale et des différentes sections
  de Paramètres.
- Mise à jour de l'aide concernant les pleins, entretiens, rappels,
  préconisations, sauvegardes et apparence.
- Suppression de l'ancien mécanisme de copie de AIDE.md dans le dossier
  utilisateur ; l'aide embarquée devient la source utilisée par
  l'application.
- Fiabilisation du workflow GitHub Actions de release pour macOS, Linux
  et Windows.
- Publication directe des artefacts finaux et de leurs fichiers de
  contrôle, sans archives intermédiaires par système.
- Harmonisation des dépendances de build Windows avec
  requirements-build.txt.
- Suppression d'un effet de bord du build macOS qui pouvait modifier la
  casse du fichier logo dans le dépôt.
- Documentation de la release standard multi-plateforme et séparation
  du futur build macOS High Sierra.
- Aucun changement du schéma SQLite.

---

## [4.5.28] – 2026-09-12

### Modifié

- Correction du dimensionnement de la fenêtre principale pour les
  écrans de résolution 1366×768.
- Taille initiale adaptée de `1400x950` à `1280x680` et taille minimale
  ajustée de `1180x720` à `1100x620`.
- Réduction de la largeur demandée par le tableau `Entretiens`, sans
  suppression de colonne ni de fonctionnalité.
- Adaptation des colonnes extensibles du tableau `Entretiens` afin
  qu'elles utilisent plus efficacement l'espace disponible.
- Correction de la taille demandée par la zone de texte de
  `Paramètres > Aide`, qui s'adapte désormais à l'espace disponible.
- Conservation du logo, du contenu d'aide, du défilement et de
  l'organisation actuelle de l'interface.
- Aucun changement du schéma SQLite, des repositories ou des services.

---

## [4.5.27] – 2026-09-12

### Modifié

- Suppression du champ readonly `Dernier Km` de la fiche
  `Paramètres > Véhicules`.
- Le kilométrage reste déterminé automatiquement à partir de
  l'historique des pleins et des entretiens.
- Conservation de l'affichage `Dernier km` dans les cartes de la page
  `Général`.
- Conservation de `last_km_any()` et de son utilisation par les
  fonctionnalités existantes.
- Un nouveau véhicule sans plein ni entretien possède simplement un
  kilométrage inconnu jusqu'à sa première saisie.
- Aucun changement du schéma SQLite, des repositories ou des services.

---

## [4.5.26] – 2026-09-12

### Ajouté

- Ajout d'un nettoyage automatique et silencieux des photos véhicule
  orphelines au démarrage de l'application.
- Suppression limitée aux fichiers gérés par Garage correspondant au
  format `V<ID>.png` et non référencés par un véhicule existant.

### Modifié

- Vérification des références `photo_file` après l'initialisation du
  schéma SQLite et avant le chargement des véhicules.
- Conservation des fichiers non gérés par Garage, des sous-dossiers et
  des liens symboliques.
- Une erreur de nettoyage ne bloque pas le démarrage de l'application.
- Les sauvegardes exportées après démarrage ne contiennent plus les
  anciennes photos orphelines supprimées.
- Aucun changement du schéma SQLite, de l'interface ou du mécanisme
  d'import/export.

---

## [4.5.25] – 2026-09-12

### Ajouté

- Ajout de deux actions rapides `+ Plein` et `+ Entretien` sur chaque
  carte véhicule de la page `Général`.
- Sélection automatique du véhicule correspondant à la carte avant
  l'ouverture du formulaire demandé.
- Accès direct au formulaire de nouveau plein depuis `Général`.
- Accès direct au formulaire de nouvel entretien depuis `Général`.

### Modifié

- Synchronisation des actions rapides avec le mécanisme central du
  véhicule actif.
- Réinitialisation du formulaire cible lors de l'utilisation d'une
  action rapide afin de préparer une nouvelle saisie.
- Conservation de la navigation principale introduite en v4.5.24.
- Aucun changement du stockage SQLite ni de la logique métier des
  pleins et des entretiens.

---

## [4.5.24] – 2026-09-12

### Modifié

- Remplacement de la navigation principale par une barre dédiée avec
  accès à `Général`, `Pleins`, `Entretiens`, `Graphiques` et
  `Paramètres`.
- Positionnement de l'accès `Paramètres` à droite de la barre de
  navigation principale.
- Remplacement du Notebook principal par des pages permanentes
  superposées et affichées avec `tkraise()`.
- Conservation du Notebook secondaire et des sous-sections de
  `Paramètres`.
- Conservation de l'état des pages et des sous-sections lors des
  changements de navigation.
- Aucun changement de la logique métier, du stockage SQLite ou des
  repositories/services.

---

## [4.5.23] – 2026-09-12

### Modifié

- Suppression de l'ancien onglet principal `Véhicules`, devenu inutile
  après le déplacement de sa gestion vers `Paramètres > Véhicules`.
- Simplification de la navigation principale, désormais organisée en
  `Général`, `Pleins`, `Entretiens`, `Graphiques` et `Paramètres`.
- Conservation à l'identique de la gestion des véhicules dans
  `Paramètres > Véhicules`.
- Conservation des mécanismes existants de sélection et de
  synchronisation du véhicule actif.
- Aucun changement du stockage SQLite ni de la logique métier des
  véhicules.

---

## [4.5.22] – 2026-09-12

### Modifié

- Déplacement de la gestion des véhicules de l'onglet principal
  `Véhicules` vers `Paramètres > Véhicules`.
- Conservation de la sélection, de l'ajout, de la modification et de
  la suppression des véhicules dans leur nouvel emplacement.
- Conservation de la gestion des photos et des informations techniques
  des véhicules.
- Conservation des attributs et mécanismes existants de synchronisation
  avec le véhicule actif.
- Synchronisation des changements de véhicule avec les autres sections
  de l'application.
- Adaptation de l'état vide de `Général` pour orienter la création du
  premier véhicule vers `Paramètres > Véhicules`.
- Conservation temporaire de l'onglet principal `Véhicules`, désormais
  sans contenu fonctionnel, en vue de sa suppression dans un jalon
  séparé.
- Aucun changement du stockage SQLite ni de la logique métier des
  véhicules.

---

## [4.5.21] – 2026-09-12

### Modifié

- Déplacement de la configuration des types d'entretien de l'onglet
  principal `Entretiens` vers `Paramètres > Entretien`.
- Ajout d'un sélecteur de véhicule dédié dans
  `Paramètres > Entretien`.
- Synchronisation de ce sélecteur avec le véhicule actif de
  l'application.
- Conservation de la création, de la modification, de la suppression
  et de l'activation des rappels des types d'entretien.
- Conservation du formulaire et de l'historique des entretiens
  réalisés dans l'onglet principal `Entretiens`.
- Synchronisation immédiate des types configurés avec le formulaire
  de saisie d'un entretien.
- Ajout de protections minimales pour la gestion des types lorsqu'aucun
  véhicule n'est enregistré.
- Aucun changement du stockage SQLite ni de la logique métier des
  entretiens.

---

## [4.5.20] – 2026-09-12

### Modifié

- Déplacement des préconisations constructeur de l'onglet principal
  `Véhicules` vers `Paramètres > Préconisations`.
- Ajout d'un sélecteur de véhicule dédié dans
  `Paramètres > Préconisations`.
- Synchronisation de ce sélecteur avec le véhicule actif de
  l'application.
- Conservation des fonctions existantes d'ajout, de modification et
  de suppression des préconisations.
- Conservation à l'identique du stockage SQLite et de la logique
  métier des préconisations.
- Aucun autre déplacement fonctionnel dans ce jalon.

---

## [4.5.19] – 2026-09-12

### Modifié

- Déplacement de l'Aide vers `Paramètres > Aide`.
- Suppression du contrôle global `Afficher l'Aide` et de sa barre sous les onglets principaux.
- Suppression de l'ancien panneau d'Aide superposé aux cartes de l'onglet `Général`.
- Ajout d'un état vide dédié dans `Général` lorsqu'aucun véhicule n'est enregistré.
- Conservation du contenu, du défilement et du logo de l'Aide dans son nouvel emplacement.
- Ajustement du layout de l'Aide afin de conserver l'affichage complet du logo.
- Aucun changement de logique métier ou de lecture de `AIDE.md`.

---

## [4.5.18] – 2026-09-12

### Modifié

- Déplacement des commandes `Exporter une sauvegarde` et
  `Importer une sauvegarde` vers `Paramètres > Données`.
- Création d'une méthode dédiée `_build_settings_data()` pour
  construire les commandes de gestion des sauvegardes.
- Conservation à l'identique de la logique d'exportation et
  d'importation des données.
- Conservation du contrôle d'Aide dans la barre globale.
- Aucun autre déplacement fonctionnel dans ce jalon.

---

## [4.5.17] – 2026-09-12

### Modifié

- Déplacement du sélecteur de thème de l'onglet `Général` vers `Paramètres > Apparence`.
- Conservation à l'identique du comportement de changement de thème.
- Création d'une méthode dédiée `_build_settings_appearance()` pour construire les réglages d'apparence.
- Aucun autre déplacement fonctionnel dans ce jalon.

---

## [4.5.16] – 2026-09-12

### Ajouté

- Ajout d'un Notebook secondaire dans l'onglet `Paramètres`.
- Création des sections `Véhicules`, `Entretien`, `Préconisations`, `Apparence`, `Données` et `Aide`.
- Préparation de la migration progressive des fonctions existantes vers `Paramètres`.
- Aucun déplacement fonctionnel dans ce jalon.

---

## [4.5.15] – 2026-09-12

### Ajouté

- Ajout d'un nouvel onglet principal `Paramètres` dans l'interface.
- Préparation de la future réorganisation de l'interface v5.
- Conservation temporaire de tous les onglets et fonctionnalités existants.
- Aucun déplacement fonctionnel dans ce jalon.

---

## [4.5.14] – 2026-09-12

### Modifié

- Création de `graph_repository.py` pour isoler les lectures SQLite utilisées par les graphiques.
- Extraction des quatre requêtes de lecture utilisées pour la consommation, le prix du litre et les coûts d'entretien.
- Conservation dans `garage.py` des calculs statistiques, transformations de données et rendus Matplotlib.
- Conservation à l'identique des requêtes SQL, paramètres et ordres de tri.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.13] – 2026-09-12

### Modifié

- Déplacement de `_format_days()` et `compute_reminder_status()` depuis `garage.py` vers `maintenance_service.py`.
- Regroupement de la logique métier des rappels d'entretien dans le service dédié.
- Conservation à l'identique des règles de kilométrage, de périodicité, de retard, de pré-alerte, des couleurs et des textes affichés.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.12] – 2026-09-12

### Modifié

- Déplacement de `estimate_maintenance_cost_next_months()` depuis `garage.py` vers `maintenance_service.py`.
- Regroupement progressif de la logique métier d'entretien dans le service dédié.
- Conservation à l'identique des règles d'échéance, du calcul des occurrences et de l'estimation des coûts.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.11] – 2026-09-12

### Modifié

- Création de `date_utils.py` pour centraliser les helpers génériques de manipulation des dates.
- Déplacement de `_parse_iso_date()`, `_month_diff()` et `_add_months()` depuis `garage.py` vers `date_utils.py`.
- Conservation à l'identique du parsing des dates, du calcul des mois entiers et de la gestion des ajouts de mois et fins de mois.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.10] – 2026-09-12

### Modifié

- Création de `maintenance_service.py` pour isoler progressivement la logique métier liée aux entretiens.
- Déplacement de `last_km_any()` depuis `garage.py` vers `maintenance_service.py`.
- Conservation à l'identique des requêtes SQL, conversions et règles de sélection du dernier kilométrage connu.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.9] – 2026-09-12

### Modifié

- Création de `statistics_service.py` pour isoler les calculs statistiques de l'interface principale.
- Déplacement de `conso_moy_l100()` depuis `garage.py` vers `statistics_service.py`.
- Conservation à l'identique de la requête SQL, des conversions, des conditions de retour et du calcul de consommation moyenne.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.8] – 2026-09-12

### Modifié

- Extraction de la gestion des préconisations dans `preconisation_repository.py`.
- Déplacement de `list_preconisations()`, `insert_preconisation()`, `update_preconisation()` et `delete_preconisation()`.
- Conservation à l'identique des requêtes SQL, validations, horodatage, conversions, commits, fermetures de connexion et valeurs de retour.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.7] – 2026-09-12

### Modifié

- Extraction de trois lectures SQLite liées aux entretiens dans `maintenance_repository.py`.
- Déplacement de `get_last_entretien_for_type()`, `get_last_battery_voltage()` et `_recent_cost_for_type()`.
- Conservation à l'identique des requêtes SQL, conversions, valeurs de retour et appelants existants.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.6] – 2026-09-12

### Modifié

- Extraction de la gestion des types d'entretien dans `maintenance_type_repository.py`.
- Déplacement de `list_vehicle_types()`, `create_type_for_vehicle()`, `update_type()`, `delete_type_from_vehicle()` et `set_vehicle_type_enabled()`.
- Conservation à l'identique des requêtes SQL, conversions, associations véhicule/type, activation des rappels et règles de suppression des types encore référencés.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.5] – 2026-09-12

### Modifié

- Extraction du CRUD Entretiens dans `maintenance_repository.py`.
- Déplacement de `list_entretiens_full()`, `get_entretien()`, `insert_entretien()`, `update_entretien()` et `delete_entretien()`.
- Conservation à l'identique des requêtes SQL, jointures, conversions, snapshots des types d'entretien, commits, fermetures de connexion et valeurs de retour.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.4] – 2026-09-12

### Modifié

- Extraction du CRUD Pleins dans `fuel_repository.py`.
- Déplacement de `list_pleins()`, `list_pleins_lieux()`, `get_plein()`, `insert_plein()`, `update_plein()` et `delete_plein()`.
- Conservation à l'identique des requêtes SQL, conversions, commits, fermetures de connexion et valeurs de retour.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.3] – 2026-09-12

### Modifié

- Extraction des helpers `_safe_int()` et `_safe_float()` dans `value_utils.py`.
- Centralisation des conversions sécurisées d'entiers et de nombres flottants hors de `garage.py`.
- Conservation à l'identique du comportement existant des conversions.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.2] – 2026-09-11

### Modifié

- Extraction du CRUD des véhicules dans le module `vehicle_repository.py`.
- Déplacement des opérations de lecture, ajout, modification et suppression des véhicules hors de `garage.py`.
- Conservation à l’identique du comportement des photos et des suppressions liées aux véhicules.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.1] – 2026-09-11

### Modifié

- Extraction de l'initialisation et de la connexion SQLite dans le module `database.py`.
- Extraction de la gestion du schéma et des migrations SQLite dans `database.py`.
- Conservation à l'identique de l'ordre d'initialisation de la base de données.
- Aucun changement fonctionnel ou visuel.

---

## [4.5.0] – 2026-09-11

### Modifié

- Début de la réorganisation interne de Garage en modules dédiés.
- Extraction de la gestion des chemins et des constantes associées dans `app_paths.py`.
- Aucun changement fonctionnel ou visuel.

---

## [4.4.24] – 2026-09-10

### Ajouté

- Importation d’une sauvegarde Garage depuis une archive ZIP.
- Validation de l’archive et de la base SQLite avant toute modification des données.
- Création automatique d’une sauvegarde de sécurité avant importation.

### Modifié

- Lors d’une restauration, la base de données et les photos des véhicules sont remplacées par celles de la sauvegarde sélectionnée.
- En cas d’échec pendant l’importation, les données précédentes sont restaurées automatiquement.
- Après une restauration réussie, Garage demande un redémarrage pour utiliser les données importées.

---

## [4.4.23] – 2026-09-10

### Ajouté

- Ajout d'un export de sauvegarde complet.
- Copie cohérente de `garage.db` via l'API SQLite backup.
- Inclusion du dossier `vehicle_photos`.
- Export dans une archive ZIP choisie par l'utilisateur.

---

## [4.4.22] – 2026-06-06

### Modifié

- Retrait du build macOS legacy du workflow GitHub Actions automatique faute de runner `macos-13` disponible.
- Passage des builds GitHub Actions courants à Python 3.12.
- Documentation du build macOS legacy comme build local sur ancien macOS ou runner auto-hébergé.

---

## [4.4.21] – 2026-06-06

### Corrigé

- Correction du build moderne macOS et Linux avec Pillow compatible Python 3.13.

---

## [4.4.20] – 2026-06-06

### Modifié

- Mise en place de profils de build macOS moderne et legacy depuis le même code.
- Ajout de dépendances de build séparées pour macOS legacy.
- Build multi-OS lancé depuis `main` avec le même code applicatif.

---

## [4.4.19] – 2026-05-29

### Feat

- Creation d'une branche pour macOSX 11.0.0 (Big Sur)

---

## [4.4.17] – 2026-05-28

### Corrigé

- Compatibilité Tk et matplotlib pour macOSX 11.0.0 (Big Sur).

---

## [4.4.16] – 2026-05-28

### Corrigé

- Tk et matplotlib doivent fonctionner
- Contour du vehicule séléctionné 
- Les entretiens longs passe en orange le dernier mois.

---

## [4.4.15] – 2026-05-28

### Corrigé

- Mise a plats de la versions

---

## [4.4.14] – 2026-05-28

### Corrigé

- Les Builds embarquent TKinter et matplotlib

---

## [4.4.13] – 2026-05-28

### Corrigé

- Couleurs des Decomptes.
---

## [4.4.12] – 2026-05-28

### Corrigé

- Decomptes de temps d'entretiens fonctionnels.

---

## [4.4.11] – 2026-05-18

### Amélioré

- Releases GitHub plus lisibles avec titre Garage et artefacts groupés par OS.

---

## [4.4.10] – 2026-05-18

### Corrigé

- Utilisation d'un runner macOS Intel plus disponible pour le build GitHub Actions.

---

## [4.4.9] – 2026-05-18

### Corrigé

- Stabilisation des runners GitHub Actions pour le build multi-OS.

---

## [4.4.8] – 2026-05-18

### Ajouté

- Build multi-OS automatisé via GitHub Actions.

---

## [4.4.7] – 2026-05-18

### Corrigé

- Démarrage possible sur une nouvelle installation macOS sans base existante.
- Vérification de l'inclusion de `garage_empty.db` dans le build macOS.

---

## [4.4.6] – 2026-01-07

### Modifié

 - Quand un entretien est à faire dans moins d'un mois, on indique le nombre de jours
   et plus "0 mois" --> et aujourd'hui à la plae de 0 jours

 - L'entretien "Tension Batterie" est placé en premier des entretiens, les autres en ordre alphabetique  

---

## [4.4.4] – 2026-01-07

### Corrigé

 - Ajustement pour faire fonctionner les thèmes sous macOS

---

## [4.4.3] – 2026-01-07

### Corrigé

- Limitation de la taille des Photos dans l'onglet Général pour windows 
- Compression possible des listes entretiens sans pousser le bas de la page hors de l'écran

---

## [4.4.2] – 2026-01-07

### Corrigé

 - Supperssion du tiret au dessus des années de la courbe €/litre 
 - Modification du calcul de la taille des Photos dans l'onglet Général pour windows

### Amélioré

- Suppression du message en bas "garage.db"

---

## [4.4.1] – 2026-01-07

### Ajouté

 - Le type d'énergie selon le vehicule est affiché dans le titre de la courbe €/litre

### Amélioré
 
 - Sélection et ajustement des couleurs de 16 Thèmes
 - Ajustement de la largeur de le combobox sélecteur de thèmes

---

## [4.4] – 2026-01-06

### Ajouté

 - Fonction selecteur de thèmes 

 ---

## [4.3.4] – 2026-01-05

### Ajouté

 - Reglage des couleurs facile pour chaque OS

### Corrigé

 - Taille du logo dans aide 
 - Plus de crash si zero véhicule
 - Fichier .gitignore

### Amélioré

 - Couleur de l'interface sous Linux
 - Ajustement des couleurs de polices suivant les zones

---

## [4.3.3] – 2026-01-05

### Corrigé

 - Chemins d'accès photos & garage.db pour Linux 
 
### Amélioré

 - AIDE.md

---

## [4.3.2] – 2026-01-04

### Corrigé

 - Noms des photos importées: Véhicule n°1 = V1.###
 - Les photos importées restent en miniatures aprés l'enregistrement 

---

## [4.3.1] – 2026-01-04

### Ajouté

 - Changement de l'infrastructure du projet: 

 - création du dossier \Build (vide) et \data (garage_empty.db)
 - création d'un fichier requirerments.txt (pillow + matplotlib)
 - création d'un .gitignore --> pour laisser des chose en local (photos & db perso...)

---

## [4.3] – 2026-01-03

### Ajouté

- Onglet "Graphiques" comporte pour l'instant trois graphiques:
- la conso L/100km 
- L'évolution des prix des entretiens et des réparations par années
- L'évolution du prix du carburant par années

---

## [4.2.3] – 2026-01-02

### Ajouté

- Calcul de coût d'entretien moyen par an.

### Corrigé

- Les photos sont redimenssionées afin de ne pas modifier l'apparence des fenêtres
- Le programme ne crash plus si suppression du seul véhucule
- Redimensionne sans croper les photos
- Calcul du coût d'entretien moyen par an = moyenne par an & moyenne des années

---

## [4.2.2] – 2026-01-01

### Ajouté

- Édition et mise à jour du README

### Corrigé

- Problème de bouton manquant dans l'onglet entretien
- Problème d'affichage du logo de la page aide sous Linux

---

## [4.2.2] – 2025-12-31

### Ajouté

- Possibilité de changer la couleur la taille de la police & la couleur du fond de l'AIDE (au début du code)

---

## [4.2] – 2025-12-30

### Ajouté

-Fichier AIDE.md affiché au démarage si pas de véhicule (1er démarage) + case à cocher pour l'afficher

---

## [4.1.2] – 2025-12-30

### Ajouté

-Nouvelle regle concernat les Rappels: si un entretien dans la liste des rappels a une règle de fréquence qui est
supérieur à 6 mois et qu'il faut le faire dans moins de 6 mois alors il passe en orange.

-Augmentation de la taille de police et changement de la couleur de la ligne "Coût à prevoir" dans l'onglet general.

---

## [4.1.1] – 2025-12-30

### Modifié 

-Mise en page onglet vehicule et général

---

## [4.1.0] – 2025-12-30

### Ajouté

-Une section "Préconisations Constructeur" dans l'onglet vehicule pour y noter
 par exemple: type d'huile, pression des pneumatiques, frequences des entretiens...

--- 

## [4.0.0] – 2025-12-19

### Ajouté 

-Refonte de l'onglet Entretien, on y gerera désormais la definition des differents types d'entretien
 selon le vehicule en y renseigant une description, une periodoicité et une case à cocher pour que le rappel  
 apparaisse dans l'onglet "Général". 


---

## [3.1.2] – 2025-12-18

### Modifié 

- Correction de fautes et soucis de lisibilité.
- Ré affiche la conso moyenne qui été pérdue dans les méandres de la v3.0

---

## [3.1.1] – 2025-12-18

### Ajouté

- Prise en compte des KM de la section entretien pour afficher dans KM actuels sous la photo de 
 la voiture. 

---

## [3.1.0] – 2025-12-18

### Ajouté

- Fonction de previsionnel des couts futurs (dernier prix des carburants enregistrés, estimation
  du cout des entretiens à venir dans les 6 prochains mois en ce basant sur les dernieres factures.

---

## [3.0.1] – 2025-12-17

### Modifié

- Placement de texte, tailles et styles de police

---

## [3.0.0] – 2025-12-17

### Modifié

- Refonte des onglets: un onglet general avec les photos des voitures affichées, leurs KM à la derniere
  M-A-J plein ou Entretien, les details technique des voitures, la conso moyenne au litre / 100km, et les alertes.

Les autres onglets sonts:
- Les pleins
- les Entretiens
- Les options (à venir)

---

## [2.5.4] – 2025-12-17

### Ajouté

- Rappels d’entretien intelligents :
  - Affichage *à faire dans XXXX KM, ou le JJ/MM/AAAA* si l’entretien n’est pas encore dû
  - Affichage *aurait dû être fait depuis XXXX KM ou le JJ/MM/AAAA* si l’entretien est dépassé
- Prise en compte du kilométrage **et** de la date pour les rappels (logique “OU”)
- Migration automatique des anciennes tables `entretien` sans colonne `id`

### Amélioré

- Mise en page principale :
  - Coût moyen annuel carburant et entretien affichés **sous la photo du véhicule**
  - Rappels d’entretien **centrés sous les boutons**
- Lisibilité renforcée :
  - Kilométrage véhicule affiché en police plus grande
  - Coûts moyens annuels affichés en police plus grande
- Calculs robustes :
  - La consommation moyenne ignore automatiquement les segments avec plein manquant

### Corrigé

- Erreurs SQLite liées aux schémas anciens (`no such column: id`)
- Problème de variable masquant la fonction `last_km`
- Fichiers corrompus suite à des injections involontaires de regex

---

## [2.5.0] – 2025-12-16

### Ajouté

- Gestion multi-véhicules (jusqu’à 5 véhicules)
- Fiches véhicule complètes :
  - Nom (pseudo), marque, modèle, motorisation, énergie, année, immatriculation, photo
- Section **Entretien** avec :
  - Date (JJ/MM/AA)
  - Kilométrage
  - Intervention : Entretien / Réparation / Entretien + Réparation
  - Détails d’intervention
  - Coût
  - Effectué par
- Calcul du coût moyen annuel carburant et entretien

---

## [2.4.0]

### Ajouté

- Ajout du kilométrage dans les entretiens
- Gestion combinée entretien + réparation
- Détection silencieuse des pleins manquants pour fiabiliser les calculs

---

## [2.3.0]

### Ajouté

- Module Entretien (première version)
- Séparation claire Pleins / Entretien / Lieux / Véhicules

---

## [2.0.0]

### Ajouté

- Interface graphique Tkinter
- Gestion des pleins par véhicule
- Historique et calculs de base

---

## [1.x]

### Initial

- Prototype mono-véhicule
- Suivi simple des pleins
