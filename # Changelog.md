# Changelog

Toutes les modifications notables de ce projet sont documentées dans ce fichier.  
Le format est inspiré de *Keep a Changelog* et le versionnement suit une logique sémantique pragmatique.

---
## [3.1.0] – 2025-12-18

-Ajout d'une fonction de previsionnel des couts futurs (dernier prix des carburants enregistrés, estimation
 du cout des entretiens à venir dans les 6 prochains mois en ce basant sur les dernieres factures en prenant
en compte que si la facture est d'avant 2023, on ajoute 20% pour l'inflation)

## [3.0.1] – 2025-12-17

-Changement de placement de texte, tailles et styles de police

## [3.0.0] – 2025-12-17
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
