# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.  
Le format est inspiré de *Keep a Changelog* et le versionnement suit une logique sémantique pragmatique.

---
## [4.2.3] – 2026-01-01

### Ajouté

- Ajout du calcul de coût d'entretien moyen par an.

### Corrigé

- Les photos sont redimenssionées afin de ne pas modifier l'apparence des fenêtres
- Le programme ne crash plus si suppression du seul véhucule

## [4.2.2] – 2026-01-01

### Ajouté

- Édition et mise à jour du README

### Corrigé

- Problème de bouton manquant dans l'onglet entretien
- Problème d'affichage du logo de la page aide sous Linux

## [4.2.1] – 2025-12-31

### Ajouté

- Possibilité de changer la couleur la taille de la police & la couleur du fond de l'AIDE (au début du code)

## [4.2] – 2025-12-30

### Ajouté

-Fichier AIDE.md affiché au démarage si pas de véhicule (1er démarage) + case à cocher pour l'afficher


## [4.1.2] – 2025-12-30

### Ajouté

-Nouvelle regle concernat les Rappels: si un entretien dans la liste des rappels a une règle de fréquence qui est
supérieur à 6 mois et qu'il faut le faire dans moins de 6 mois alors il passe en orange.

-Augmentation de la taille de police et changement de la couleur de la ligne "Coût à prevoir" dans l'onglet general.

## [4.1.1] – 2025-12-30

### Modifié 

-Mise en page onglet vehicule et général

## [4.1.0] – 2025-12-30

### Ajouté

-Une section "Préconisations Constructeur" dans l'onglet vehicule pour y noter
 par exemple: type d'huile, pression des pneumatiques, frequences des entretiens...

## [4.0.0] – 2025-12-19

### Ajouté 

-Refonte de l'onglet Entretien, on y gerera désormais la definition des differents types d'entretien
 selon le vehicule en y renseigant une description, une periodoicité et une case à cocher pour que le rappel  
 apparaisse dans l'onglet "Général". 


## [3.1.2] – 2025-12-18

### Modifié 

- Correction de fautes et soucis de lisibilité.
- Ré affiche la conso moyenne qui été pérdue dans les méandres de la v3.0

## [3.1.1] – 2025-12-18

### Ajouté

- Prise en compte des KM de la section entretien pour afficher dans KM actuels sous la photo de 
 la voiture. 

## [3.1.0] – 2025-12-18

### Ajouté

- Fonction de previsionnel des couts futurs (dernier prix des carburants enregistrés, estimation
  du cout des entretiens à venir dans les 6 prochains mois en ce basant sur les dernieres factures.

## [3.0.1] – 2025-12-17

### Modifié

- Placement de texte, tailles et styles de police

## [3.0.0] – 2025-12-17

### Modifié

- Refonte des onglets: un onglet general avec les photos des voitures affichées, leurs KM à la derniere
  M-A-J plein ou Entretien, les details technique des voitures, la conso moyenne au litre / 100km, et les alertes.

Les autres onglets sonts:
-Les pleins
-les Entretiens
-Les options (à venir)

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
