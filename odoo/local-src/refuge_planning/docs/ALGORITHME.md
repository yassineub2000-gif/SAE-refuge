# Algorithme de génération — Planning Refuge des Aventuriers

Livrable 4 du cahier des charges — §3.6 « Planning des employés ».
Cette documentation décrit le **fonctionnement réel** de l'algorithme implémenté
dans [refuge_planning_generator.py](/home/matski/refuge-des-aventuriers/odoo17-iut/odoo/local-src/refuge_planning/models/refuge_planning_generator.py).

L'objectif du générateur est de proposer un planning hebdomadaire :

- cohérent avec les **disponibilités** saisies ;
- conforme aux **contraintes légales et métier** ;
- modifiable ensuite manuellement par le gérant ;
- lisible et défendable en soutenance.

## Objectif

Le bar est ouvert du **mardi au dimanche**, de **10h00 à 01h00**, soit :

- `6 jours`
- `15h` d'ouverture par jour
- `90h` de couverture à assurer sur une semaine

L'équipe comporte **4 employés**, tous à **24h/semaine**, soit :

- `4 × 24h = 96h` de capacité théorique hebdomadaire

L'algorithme cherche donc à construire une semaine :

- avec **au moins un barman présent à tout instant** ;
- sans dépasser les capacités individuelles ;
- en respectant les repos légaux ;
- en utilisant uniquement les disponibilités réellement déclarées.

## Données d'entrée

Le générateur s'appuie sur trois sources principales.

### 1. Les employés

Chaque employé apporte :

- son identité ;
- son volume horaire contractuel hebdomadaire ;
- son contrat Odoo, utilisé comme source prioritaire pour les heures hebdo.

Dans le code :

- le contrat est lu via `employee.contract_id.refuge_weekly_hours`
- à défaut, on retombe sur `employee.refuge_weekly_hours`
- en dernier recours, le fallback vaut `24h`

### 2. Les disponibilités

Les disponibilités sont stockées dans `refuge.planning.availability`.

Chaque ligne correspond à :

- un employé ;
- un jour de semaine ;
- un statut :
  - `available`
  - `unavailable`
- un `slot_mask` de 30 caractères

Le `slot_mask` est la vraie source de vérité :

- `30 slots`
- `1 slot = 30 minutes`
- amplitude : `10h00 → 01h00`

Exemple :

- slot `0` = `10:00–10:30`
- slot `1` = `10:30–11:00`
- slot `29` = `00:30–01:00`

### 3. Les shifts déjà existants

Le générateur prend aussi en compte les shifts déjà présents sur la semaine cible.

Deux cas :

- `is_generated = True` : ils sont supprimés avant une nouvelle génération
- `is_generated = False` : ils sont conservés comme **shifts manuels verrouillés**

Ces shifts manuels pèsent déjà dans :

- le calcul des heures hebdomadaires consommées ;
- la couverture de la journée ;
- la règle des `11h` de repos.

## Contraintes respectées

Les contraintes dures implémentées sont les suivantes :

| Contrainte | Valeur |
|---|---|
| Lundi fermé | aucun shift |
| Durée max par jour | `10h` par employé |
| Repos minimal | `11h` entre deux shifts |
| Volume hebdo | `24h` contractuelles |
| Granularité minimale | `30 min` |
| Taille minimale d'un shift généré | `2h` |

En pratique, le générateur travaille avec ces constantes :

- `SLOT_COUNT = 30`
- `MAX_SLOTS_PER_DAY = 20` → `10h`
- `MIN_REST_SLOTS = 22` → `11h`
- `MIN_SHIFT_SLOTS = 4` → `2h`

## Principe général

L'algorithme ne génère pas directement “un tableau final”. Il procède en
plusieurs couches.

### Vue d'ensemble

1. Il prépare la semaine cible.
2. Il retire les anciens brouillons générés.
3. Il conserve les shifts manuels.
4. Il reconstruit la semaine **jour par jour**.
5. Pour chaque journée, il cherche d'abord une **couverture complète**.
6. Si cette couverture complète est impossible, il calcule la **meilleure couverture partielle**.
7. Il convertit les segments trouvés en vrais `refuge.planning.shift`.

## Étape 1 — Préparation de la semaine

La méthode principale est :

```python
generate_week(monday)
```

Elle commence par :

- calculer la semaine cible (`monday` → `monday + 6 jours`) ;
- supprimer uniquement les shifts auto-générés de cette semaine ;
- charger les 4 employés du bar ;
- charger toutes leurs disponibilités ;
- convertir les heures hebdomadaires en **nombre de demi-heures** ;
- charger les shifts manuels déjà présents.

Pourquoi convertir en demi-heures :

- tout le solveur travaille dans une unité homogène ;
- cela simplifie les comparaisons ;
- cela évite les erreurs de flottants.

Exemple :

- `24h` deviennent `48 slots`
- `10h` deviennent `20 slots`
- `11h` deviennent `22 slots`

## Étape 2 — Intégration des shifts manuels

Les shifts manuels sont injectés dans le solveur comme des segments déjà fixes.

Pour chaque shift manuel :

- on calcule son `start_slot`
- on calcule son `end_slot`
- on le range dans `preserved_by_day`
- on ajoute sa durée au compteur `planned_slots[employee]`

Conséquence :

- un shift manuel n'est jamais écrasé ;
- une partie de journée peut déjà être couverte avant même le calcul automatique ;
- un employé peut déjà avoir consommé une partie de son quota hebdomadaire.

## Étape 3 — Résolution semaine par semaine

Le cœur du solveur est `_solve_week(...)`.

Il traite les jours ouverts dans l'ordre :

- mardi
- mercredi
- jeudi
- vendredi
- samedi
- dimanche

Pour chaque jour :

- il récupère les segments manuels déjà présents ;
- il cherche toutes les solutions complètes possibles pour cette journée ;
- puis il choisit la meilleure combinaison pour le reste de la semaine.

On a donc une **recherche récursive** sur la semaine :

- chaque choix fait sur une journée influence les jours suivants ;
- notamment parce qu'il consomme :
  - du temps hebdomadaire ;
  - des repos.

## Étape 4 — Résolution d'une journée complète

La méthode `_enumerate_day_solutions(...)` cherche toutes les solutions
journalières couvrant entièrement l'amplitude `10h → 01h`.

Elle utilise un backtracking.

### Comment la journée est parcourue

Le solveur avance slot par slot :

- s'il rencontre un slot déjà couvert par un shift manuel, il saute directement à la fin de ce shift ;
- sinon, il cherche quels employés peuvent commencer un segment à cet instant.

### Construction du contexte du jour

La méthode `_build_day_context(...)` prépare :

- `fixed_lookup` : quels slots sont déjà couverts par un shift manuel ;
- `used_employees` : quels employés ont déjà un shift ce jour ;
- `intervals_by_emp` : les plages continues de disponibilité de chaque employé ;
- `next_fixed_start` : prochain segment manuel à ne pas traverser.

### Génération des options sur un slot

La méthode `_day_slot_options(...)` construit les segments envisageables à partir d'un slot donné.

Un employé est candidat seulement si :

- il n'a pas déjà un shift ce jour ;
- il est disponible à ce slot ;
- il respecte les `11h` de repos ;
- il lui reste assez d'heures hebdomadaires ;
- il peut tenir au moins `2h` de shift ;
- le segment ne chevauche pas un segment manuel futur.

Le solveur ne teste pas n'importe quelle fin de shift. Il borne les fins possibles avec :

- la fin de la disponibilité continue ;
- le prochain shift manuel déjà fixé ;
- le quota journalier max ;
- le quota hebdomadaire restant ;
- certains points de coupure utiles correspondant au début de disponibilité d'autres employés.

Cela réduit fortement le nombre de combinaisons à explorer.

## Étape 5 — Choix de la meilleure semaine complète

Quand plusieurs solutions complètes existent pour une journée, `_solve_week(...)`
ne prend pas la première venue.

Il évalue chaque branche avec trois critères, dans cet ordre :

1. **le moins de créneaux non couverts sur le reste de la semaine**
2. **la plus grande capacité restante**

Dans le code, cela correspond à :

```python
meta = (len(uncovered), remaining_capacity)
```

Autrement dit :

- priorité absolue à la couverture ;
- ensuite, on garde de la souplesse pour les autres jours.

## Étape 6 — Si une journée complète est impossible

Si `_enumerate_day_solutions(...)` ne trouve aucune solution complète, le solveur
ne rend pas la journée vide.

Il bascule dans `_best_partial_day_solution(...)`.

Cette méthode cherche la **meilleure solution partielle** :

- elle essaie toujours de placer des segments valides ;
- elle peut aussi “sauter” un slot si aucun segment n'est possible ;
- elle compare les solutions partielles avec `_pick_better_partial(...)`.

Les critères de choix sont alors :

1. **le moins de slots non couverts**
2. **la plus grande quantité d'heures effectivement couvertes**

Cela permet un comportement beaucoup plus réaliste :

- si une journée ne peut pas être couverte à 100 %,
- l'outil remplit ce qu'il peut proprement,
- au lieu d'abandonner tout le jour.

## Étape 7 — Création des shifts Odoo

Une fois la semaine résolue, chaque segment trouvé est converti en record
`refuge.planning.shift`.

Pour chaque segment :

- le `start_slot` est transformé en heure flottante ;
- le `end_slot` est transformé en heure flottante ;
- si on dépasse minuit, l'heure de fin est rebasculée dans le format Odoo (`1.0` au lieu de `25.0`) ;
- le shift est créé en état `draft` ;
- le champ `is_generated` est positionné à `True`.

## Pourquoi cette approche a été choisie

Cette approche est un bon compromis pour la SAÉ.

### Avantages

- elle respecte précisément les contraintes métier ;
- elle produit des shifts continus, donc réalistes en exploitation ;
- elle reste compréhensible en soutenance ;
- elle tient compte des modifications manuelles du gérant ;
- elle peut expliquer les trous éventuels au lieu de masquer le problème.

### Limites

- ce n'est pas un solveur mathématique global type ILP ;
- la recherche reste bornée à l'instance actuelle ;
- elle suppose un seul shift par employé et par jour côté génération automatique ;
- elle ne cherche pas à optimiser des objectifs RH plus fins :
  - équilibre matin/soir
  - confort employé
  - rotation des week-ends

## Complexité et performance

Le problème est combinatoire par nature.

Pour rester performant, l'algorithme réduit l'espace de recherche grâce à :

- la granularité fixe de `30 min` ;
- le plafond `10h/jour` ;
- le minimum `2h` par shift ;
- l'arrêt sur les shifts manuels ;
- les coupures de segments sur les vraies frontières utiles.

Dans le contexte du projet :

- seulement `4 employés`
- `6 jours ouverts`
- `30 slots par jour`

la recherche reste suffisamment légère pour être exécutée à la demande depuis l'interface OWL.

## Résumé exécutable

En une phrase :

> le générateur efface les brouillons auto, garde les shifts manuels, transforme les disponibilités en segments de demi-heures, explore jour par jour les combinaisons valides, privilégie la couverture complète, puis crée des shifts Odoo modifiables par le gérant.

## Invocation

Depuis l'interface Odoo :

- menu `Le Refuge des Aventuriers > Planning > Générer la semaine`
- ou application OWL `/refuge/planning`

Depuis le shell Odoo :

```python
from datetime import date

gen = env["refuge.planning.generator"].create({"week_start": "2026-04-27"})
result = gen.generate_week(date(2026, 4, 27))
print(result)
```

Format de retour :

```python
{
    "created": 15,
    "uncovered": [],
    "shift_ids": [1, 2, 3],
}
```
