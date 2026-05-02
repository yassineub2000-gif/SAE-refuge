# Algorithme de génération — Planning Refuge des Aventuriers

Livrable 4 du cahier des charges — §3.6 « Planning des employés ».
La consigne précise explicitement que *le choix algorithmique fait partie de
l'évaluation*. Ce document décrit le raisonnement, les compromis retenus et
les limites de la solution.

## Entrées

- **4 employés** (2 barmen, 2 barmaids), tous en CDI 20h/semaine.
- Pour chaque employé, une **disponibilité par jour** (7 lignes/semaine) avec :
  - `status` : `available` (O), `on_request` (~), `unavailable` (✕)
  - `hour_preference` : `morning` (10-18), `evening` (18-01), `flexible`
- Horaires d'ouverture imposés : **Mardi → Dimanche, 10h00 → 01h00**.

## Contraintes dures (cahier des charges §3.6)

| Contrainte | Valeur | Source |
|---|---|---|
| Durée max par jour et par employé | 10 h | PDF §3.6 |
| Repos minimum entre deux shifts | 11 h | PDF §3.6 |
| Volume contractuel hebdo | 20 h (tolérance +1 h) | PDF §3.6 |
| Lundi fermé | Pas de shift | PDF §3.6 |
| Barman présent sur chaque créneau | ≥ 1 | PDF §3.6 |

## Découpage en créneaux

Nous avons choisi un **découpage fixe à 2 créneaux par jour ouvert** :

- **Matin** : 10h00 → 18h00 (8 h)
- **Soir**  : 18h00 → 01h00 (7 h, franchit minuit)

Ce découpage suit directement les préférences horaires du fichier Excel fourni :
Pierre (10h-18h), Marlène (18h-01h), Anthony (flexible), Julie (après 16h).
Il évite de générer des micro-shifts difficiles à lire et simplifie le contrôle
des contraintes.

**Volume offert** : 6 jours × (8h + 7h) = **90 h/semaine**.
**Besoin contractuel** : 4 × 20 = **80 h/semaine**.
Marge de 10 h → tous les créneaux peuvent être couverts en respectant les 20 h.

## Stratégie — algorithme glouton (greedy)

Pour chaque créneau (dans l'ordre Mardi → Dimanche, Matin puis Soir) :

1. On calcule un **score** pour chaque employé candidat.
2. On retient le **score maximum** parmi ceux qui respectent les contraintes dures.
3. En l'absence de candidat valide, le créneau est signalé comme **non couvert**
   dans le rapport retourné (il n'est pas créé).

### Fonction de scoring

```
base = 100       si status == "available"
     = 40        si status == "on_request"
     = -∞        si status == "unavailable"

score = base
     + 30        si hour_preference == créneau (matin/soir)
     + 10        si hour_preference == "flexible"
     - 10 × (heures_planifiées_jusqu'ici / 20)   # équité
     + 5         si heures_restantes_avant_20h >= durée_créneau
```

### Validation des contraintes dures (veto)

Un candidat est éliminé (score = `-∞`) si :

- Son `status` est `unavailable`.
- Son cumul journalier avec ce créneau dépasse **10 h**.
- L'écart avec son dernier shift (veille ou même jour) est **< 11 h**.
- Il y a chevauchement avec un shift déjà planifié.
- Son cumul hebdo dépasse **20 h + 1 h** (tolérance).

### Idempotence & conservation des shifts manuels

La méthode `generate_week(monday)` commence par **supprimer uniquement les
shifts `is_generated = True`** de la semaine cible. Les shifts ajoutés à la
main par le gérant (via la vue calendar/tree) sont **conservés** et pris en
compte dans les contraintes de repos/cumul.

## Compromis et limites

### Ce que l'algorithme fait bien

- Déterministe et rejouable : mêmes entrées → mêmes sorties.
- Lisible (une fonction de score, quelques vetos) : défendable en soutenance.
- Rapide : complexité O(jours × créneaux × employés) = O(7 × 2 × 4) = **56 évaluations**.
- Respecte strictement les 5 contraintes dures ou signale explicitement un
  créneau non couvert plutôt que de les violer silencieusement.

### Ce qu'il ne fait pas

- **Pas d'optimisation globale** : un choix glouton précoce peut forcer un
  créneau suivant à rester vide même si une autre combinaison tenait. Pour
  l'instance actuelle (4 employés, 12 créneaux), ça fonctionne bien ; sur un
  bar plus grand, une formulation en ILP (ex. OR-Tools) ou un backtracking
  serait pertinent.
- **Pas de gestion des congés / jours fériés** : hors périmètre SAÉ.
- **Pas de lissage matin/soir par employé** : on peut donner deux matinées
  consécutives au même employé si c'est le meilleur score. Un terme
  anti-monotonie serait facile à ajouter si le client le demande.
- **Pas de séparation barman / barmaid** : le bar est supposé ne pas avoir de
  règle de parité imposée (le cahier des charges demande seulement « au moins
  un barman présent »).

## Invocation

Depuis l'interface Odoo : menu *Le Refuge des Aventuriers → Planning → Générer
la semaine* ou via l'app OWL */refuge/planning* (bouton "Générer").

Depuis le shell Odoo :

```python
gen = env["refuge.planning.generator"].create({"week_start": "2026-04-27"})
result = gen.generate_week(date(2026, 4, 27))
# result = {"created": 11, "uncovered": [("2026-04-29", "Soir 18h-01h")], ...}
```
