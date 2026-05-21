# Journal IA — SAÉ 6.Integ.01 Le Refuge des Aventuriers

Ce fichier recense les usages significatifs d'IA (ChatGPT, Claude, Copilot, etc.)
pendant le projet. Il respecte le format demandé dans la section 5 du cahier des
charges : **Prompt utilisé · Ce que l'IA a produit · Ce qu'on a modifié · Ce
qu'on a appris**.

Les entrées ci-dessous sont volontairement regroupées en grands prompts : chacune
correspond à un bloc fonctionnel défendable en soutenance et couvre les
fonctionnalités réellement présentes dans le dépôt.

---

## Entrée 1 — 2026-04-22 — Analyse du cahier des charges et cadrage global

**Prompt utilisé**
> « Lis le PDF `docs/SAE6 Refuge Aventuriers.pdf` et le fichier de données du
> client. Résume les exigences, les livrables, les contraintes techniques Odoo /
> OWL, puis propose une architecture de modules pour couvrir toute la mission :
> configuration Odoo, commande QR, espace barman et planning. »

**Ce que l'IA a produit**
L'IA a extrait les deux grands volets du projet :

- intégration Odoo native : clients, fidélité, produits, stock, achats,
  réapprovisionnement, POS ;
- développement OWL : commande sur table par QR Code, espace barman temps réel,
  planning hebdomadaire des employés.

Elle a aussi synthétisé les livrables :

- modèle de données ;
- environnement Odoo configuré ;
- application OWL de commande sur table ;
- application OWL de planning ;
- journal IA.

Une architecture en trois modules a été proposée :

- `refuge_aventuriers` pour le socle métier Odoo ;
- `refuge_table_order` pour les tables, QR codes, commandes et espace barman ;
- `refuge_planning` pour les disponibilités, shifts et génération de planning.

**Ce qu'on a modifié**
Nous avons gardé cette architecture en trois modules, mais nous l'avons adaptée
au code Odoo réel :

- le POS Odoo et l'application QR écrivent dans `pos.order`, conformément à la
  contrainte d'architecture du PDF ;
- les commandes QR ne sont pas payées en ligne : le paiement reste au comptoir ;
- le planning a été documenté dans `refuge_planning/docs/ALGORITHME.md` car le
  cahier des charges évalue explicitement la logique de génération.

**Ce qu'on a appris**
- Le PDF ne demande pas seulement une interface : il demande une migration ERP
  cohérente, avec des données exploitables dans les modules Odoo natifs.
- La cohabitation POS + OWL est la contrainte centrale : créer un modèle de
  commande séparé aurait compliqué la fidélité, le stock et la soutenance.
- Le journal IA doit montrer l'esprit critique : il faut documenter ce que l'IA
  propose, ce qu'on corrige, et pourquoi.

---

## Entrée 2 — 2026-04-22 — Environnement Odoo et transformation du template initial

**Prompt utilisé**
> « Le dossier `odoo17-iut` vient d'un ancien projet. Vérifie qu'il démarre,
> identifie ce qui reste du template précédent, renomme proprement le projet en
> Refuge des Aventuriers, puis prépare une base locale Odoo utilisable pour le
> développement et la démo. »

**Ce que l'IA a produit**
L'IA a inspecté la stack locale :

- `docker-compose.yml` avec services Odoo, PostgreSQL, nginx et Mailhog ;
- addons locaux montés dans `/odoo/local-src` ;
- base cible `refuge_aventuriers` ;
- ancien module école `tetras_school_management` encore présent dans certains
  fichiers.

Elle a proposé une stratégie de nettoyage :

- renommer les namespaces et routes hérités du template ;
- conserver les volumes Docker existants ;
- installer les modules locaux dans la bonne base ;
- vérifier les URLs exposées par Docker.

**Ce qu'on a modifié**
Nous avons remplacé l'ancien contexte école par le contexte bar :

- noms de modules, routes, menus et bundles d'assets adaptés au Refuge ;
- création des modules `refuge_aventuriers`, `refuge_table_order` et
  `refuge_planning` dans `odoo/local-src` ;
- installation/mise à jour via la base Docker active `refuge_aventuriers`.

Un point important a été corrigé plus tard : certaines commandes avaient été
lancées sur une ancienne base `odoodb3`. La vraie base utilisée par l'interface
était `refuge_aventuriers`, définie dans `docker-compose.yml`.

**Ce qu'on a appris**
- Avec Odoo, une mise à jour réussie sur la mauvaise base ne change rien dans
  l'interface visible.
- Les modules locaux ne sont pas automatiquement installés parce qu'ils sont dans
  l'`addons_path` : il faut les installer ou les mettre à jour explicitement.
- Les bundles OWL doivent être renommés partout : manifest, XML, JS et
  templates.

---

## Entrée 3 — 2026-04-22 — Socle Odoo : clients, produits, fournisseurs, fidélité, POS

**Prompt utilisé**
> « À partir du cahier des charges et des données fournies, crée le socle Odoo
> du bar : clients, fournisseurs, produits, catégories POS, nomenclatures de
> cocktails, fidélité, employés, contrats et configuration du POS. Utilise les
> modèles natifs Odoo dès que possible et ajoute seulement les champs métier
> nécessaires. »

**Ce que l'IA a produit**
L'IA a généré le module `refuge_aventuriers`, qui centralise la configuration
Odoo native :

- import des clients dans `res.partner` avec historique et points de fidélité ;
- import des fournisseurs et association aux produits via `product.supplierinfo` ;
- catalogue de 47 références : bières, vins, cocktails, alcools forts, softs et
  ingrédients ;
- catégories produits et catégories POS ;
- nomenclatures `mrp.bom` de type kit/phantom pour cocktails et verres d'alcool ;
- extension de `product.template` pour afficher coût de revient et marge ;
- programme de fidélité avec paliers 50, 100 et 200 points ;
- expiration des points après inactivité ;
- configuration du POS bar avec catégories visibles, ticket, paiement espèces et
  carte bancaire ;
- configuration des employés, contrats et utilisateurs liés.

**Ce qu'on a modifié**
Nous avons corrigé plusieurs propositions initiales de l'IA :

- certains champs POS imaginés n'existent pas en Odoo 17 et ont été retirés ;
- les paiements ont été configurés en cohérence avec l'usage réel : espèces et
  carte bancaire, mais sans terminal bancaire intégré, car le gérant valide le
  paiement après le TPE physique ;
- les données POS sont rechargées avec un contexte tolérant quand une session
  POS est ouverte, car Odoo bloque certaines modifications de catégories sinon ;
- les produits composés ont été liés aux bons composants stockables afin que la
  vente d'un cocktail consomme les ingrédients.

**Ce qu'on a appris**
- Odoo 17 change plusieurs APIs et champs par rapport aux exemples trouvés en
  ligne : il faut vérifier sur le code installé localement.
- Les BoM `phantom` sont le bon outil pour modéliser une recette de cocktail :
  l'utilisateur vend un Mojito, Odoo sait que le stock réel concerne le rhum, la
  menthe, le citron, etc.
- Le POS est sensible aux sessions ouvertes : une donnée XML anodine peut être
  refusée si elle modifie une configuration active.

---

## Entrée 4 — 2026-04-22 — Commande sur table QR et espace barman OWL

**Prompt utilisé**
> « Développe l'application OWL de commande sur table demandée par le PDF :
> chaque table a un QR Code, le client voit le menu par catégories, gère un
> panier et envoie une commande. Le barman doit voir les commandes sans recharger
> la page, changer leur statut, associer un client et garder la cohabitation avec
> le POS Odoo. »

**Ce que l'IA a produit**
L'IA a produit le module `refuge_table_order` :

- modèle `refuge.table` avec numéro de table, token public et QR Code ;
- synchronisation avec le POS restaurant Odoo lorsque disponible ;
- extension de `pos.order` avec source `pos/qr`, table, statut cuisine et picking
  de stock associé ;
- routes JSON-RPC publiques pour le menu client, la soumission de commande et le
  suivi ;
- routes barman pour lister les commandes, changer leur statut, chercher/créer un
  client et l'associer à une commande ;
- application OWL client responsive : menu, catégories, cards produit, panier,
  confirmation ;
- application OWL barman : liste des commandes, boutons de statut, badges stock,
  polling automatique ;
- interface d'administration QR/tables et vues backend Odoo.

**Ce qu'on a modifié**
Nous avons renforcé le code généré :

- les tokens de table ne sont pas des IDs incrémentables ;
- le polling barman nettoie ses timers OWL avec `onWillUnmount` ;
- les routes vérifient le token de table et filtrent les données renvoyées ;
- la création client côté barman évite les doublons par email ou téléphone ;
- le paiement n'est pas traité côté QR, conformément au PDF : la commande est
  envoyée au bar, puis réglée au comptoir.

**Ce qu'on a appris**
- OWL fonctionne bien pour des pages standalone, mais il faut charger les bons
  bundles Odoo et rester strict sur les expressions XML.
- Le PDF demande une mise à jour ≤ 10 secondes : un polling simple et maîtrisé
  est suffisant pour cette taille de projet.
- Écrire dans `pos.order` simplifie la démo : on peut montrer les commandes QR
  et les ventes comptoir dans la même logique métier.

---

## Entrée 5 — 2026-04-22 — Stock réel, recettes, alertes et réapprovisionnement

**Prompt utilisé**
> « Améliore toute la partie stock pour que le bar ne soit jamais à court :
> consommer les ingrédients au bon moment, gérer les seuils minimums, afficher
> des alertes compréhensibles dans Odoo, et rendre les limites paramétrables
> selon l'activité du Refuge. »

**Ce que l'IA a produit**
L'IA a proposé une logique complète autour du stock :

- les commandes QR créent un `stock.picking` lorsque le barman passe la commande
  à `Servie` ;
- les lignes de cocktails sont éclatées en composants via les BoM ;
- les mouvements de stock sont agrégés par ingrédient ;
- les règles de réapprovisionnement Odoo (`stock.warehouse.orderpoint`) sont
  créées pour les produits critiques ;
- les seuils sont calculés à partir des données de stock et du type d'article
  (ingrédient, bière/soft à rotation rapide, produit plus lent) ;
- un écran Odoo **Pilotage stock** remplace l'ancienne liste minimale :
  niveau `OK / À réapprovisionner / Critique / Rupture`, stock disponible,
  seuil minimum, stock cible, multiple de commande et quantité recommandée.

**Ce qu'on a modifié**
Nous avons corrigé plusieurs détails Odoo :

- en Odoo 17, `stock.move.quantity_done` n'est pas le bon champ : la logique a
  été adaptée à `quantity` et `picked` ;
- le calcul des quantités à recommander arrondit selon le multiple fournisseur ;
- les champs affichés dans l'UX stock écrivent réellement dans les orderpoints
  Odoo via des champs compute + inverse ;
- l'écran a été chargé dans la bonne base `refuge_aventuriers` et le serveur
  Odoo a été redémarré pour que le menu apparaisse.

**Ce qu'on a appris**
- Un simple booléen "alerte stock" n'est pas suffisant pour un utilisateur :
  il faut dire quoi commander, jusqu'à quel niveau, et avec quel degré d'urgence.
- Les seuils doivent être paramétrables, mais une base de démo doit déjà proposer
  des valeurs cohérentes pour soutenir le projet.
- Les règles de réapprovisionnement natives sont plus défendables qu'un système
  custom isolé : elles s'intègrent aux achats Odoo.

---

## Entrée 6 — 2026-04-22 — UX menu, images produits, thème et lisibilité bar

**Prompt utilisé**
> « Reprends les interfaces OWL pour qu'elles soient utilisables en conditions
> réelles : menu client mobile avec images, grosses cards, catégories lisibles,
> espace barman contrasté, thème commun Refuge, et images produit exploitables
> depuis Odoo. »

**Ce que l'IA a produit**
L'IA a amélioré l'expérience utilisateur :

- menu client en grille de cards avec image, prix, nom, description et bouton
  d'ajout ;
- catégories en navigation horizontale sticky ;
- URL d'image Odoo via `/web/image/product.product/<id>/image_256` ;
- cache-buster basé sur `write_date` pour éviter les anciennes images ;
- loader d'images produit capable d'utiliser des fichiers
  `static/src/img/products/<xmlid>.jpg|png|webp` ;
- bouton backend "Actualiser depuis fichier / SVG" sur la fiche produit ;
- thème commun `refuge_theme.css`, header partagé et styles plus cohérents ;
- espace barman plus lisible : badges stock, statuts, actions rapides, cartes
  adaptées à un usage comptoir.

**Ce qu'on a modifié**
Nous avons supprimé plusieurs choix trop décoratifs ou peu pratiques :

- les listes trop compactes ont été remplacées par des cards ;
- les images ne sont pas encodées dans le JSON : elles passent par la route
  native Odoo, plus légère et cacheable ;
- les transformations complexes ont été sorties des templates OWL pour éviter
  les erreurs de tokenizer ;
- les textes et boutons ont été ajustés pour rester lisibles sur mobile.

**Ce qu'on a appris**
- L'UX demandée par le PDF n'est pas seulement "jolie" : elle doit fonctionner
  sur téléphone, en salle, et au comptoir.
- Odoo fournit déjà beaucoup d'infrastructure utile (`/web/image`, champs image,
  miniatures) ; il faut l'utiliser au lieu de réinventer un stockage d'images.
- Les templates OWL acceptent moins d'expressions JS que du JavaScript classique :
  déplacer la logique dans les méthodes du composant évite les erreurs.

---

## Entrée 7 — 2026-04-22 — Planning employés et algorithme de génération

**Prompt utilisé**
> « Développe le module de planning demandé par le cahier des charges :
> disponibilités des quatre employés, saisie OWL, génération automatique d'une
> semaine, respect des contraintes légales, conservation des modifications
> manuelles, calendrier lisible, tests et documentation détaillée de
> l'algorithme. »

**Ce que l'IA a produit**
L'IA a produit le module `refuge_planning` :

- modèle `refuge.planning.availability` pour les disponibilités ;
- modèle `refuge.planning.shift` pour les shifts ;
- wizard `refuge.planning.generator` ;
- routes JSON-RPC pour charger la semaine, modifier les disponibilités, créer ou
  supprimer des shifts et lancer la génération ;
- application OWL `/refuge/planning` avec vues planning, disponibilités,
  calendrier hebdomadaire, heatmap, résumé et espace employé ;
- données initiales de disponibilité ;
- tests de logique planning ;
- documentation `docs/ALGORITHME.md`.

L'algorithme travaille en demi-heures sur l'amplitude 10h-01h, du mardi au
dimanche. Il respecte les contraintes clés :

- pas de shift le lundi ;
- durée maximale quotidienne ;
- repos minimal de 11h ;
- quota hebdomadaire contractuel ;
- disponibilités déclarées ;
- conservation des shifts manuels.

**Ce qu'on a modifié**
La première approche trop simple par blocs fixes a été remplacée par une logique
plus défendable :

- `slot_mask` de 30 créneaux par jour ;
- recherche de couverture complète par journée ;
- fallback de meilleure couverture partielle si impossible ;
- prise en compte des shifts manuels déjà présents ;
- création de shifts Odoo modifiables en `draft`.

La documentation a été réécrite pour expliquer le comportement réel, les
constantes, les limites et la complexité.

**Ce qu'on a appris**
- Le planning est un problème combinatoire : même avec quatre employés, il faut
  limiter l'espace de recherche.
- La soutenance exige d'expliquer les limites autant que les réussites :
  l'algorithme n'est pas un solveur ILP, mais il est traçable et adapté au
  périmètre du projet.
- Les modifications manuelles sont importantes pour le gérant : l'IA proposait
  de tout régénérer, mais il fallait préserver les shifts non générés.

---

## Entrée 8 — 2026-05-21 — Robustesse, tests, base active et mise en dépôt

**Prompt utilisé**
> « Vérifie l'ensemble du projet avant rendu : corrige les incohérences, ajoute
> les tests utiles, mets à jour la bonne base Odoo, prépare des commits propres
> par fonctionnalité et crée le dépôt GitHub public du projet. »

**Ce que l'IA a produit**
L'IA a aidé à stabiliser le projet :

- vérifications Python avec `py_compile` ;
- mises à jour Odoo via Docker ;
- tests ciblés sur le loader, le POS, la mémoire table et la logique planning ;
- diagnostic de la mauvaise base `odoodb3` versus la base active
  `refuge_aventuriers` ;
- correction du rechargement POS quand une session est ouverte ;
- création de commits par domaine fonctionnel ;
- création du dépôt GitHub public `SAE-refuge`.

**Ce qu'on a modifié**
Nous avons gardé les corrections utiles et évité les changements destructifs :

- installation/mise à jour sur la base réellement utilisée par l'interface ;
- redémarrage du service Odoo après chargement des vues ;
- remote GitHub séparé `sae-refuge`, sans supprimer l'ancien `origin` ;
- commits découpés par fonctionnalité et non en un gros commit illisible.

**Ce qu'on a appris**
- Les logs Odoo sont indispensables : une commande peut finir avec un code 0
  mais ne pas avoir chargé ce qu'on pensait si on cible la mauvaise base.
- Le `docker-compose.yml` est la source de vérité pour la base et les ports de
  l'interface locale.
- Un historique Git propre aide la soutenance : il montre les grands blocs du
  projet et facilite l'explication du travail réalisé.

---

## Synthèse finale

L'IA a été utilisée comme assistant d'analyse, de génération de code, de
débogage Odoo et de structuration documentaire. Elle a accéléré le projet, mais
plusieurs propositions ont dû être corrigées :

- champs inexistants en Odoo 17 ;
- APIs stock différentes ;
- base Odoo active mal ciblée ;
- sessions POS empêchant certaines mises à jour ;
- expressions OWL trop complexes dans les templates ;
- première logique de planning trop simple.

Le résultat final couvre les exigences principales du PDF :

- données clients, produits, fournisseurs et employés intégrées ;
- fidélité et POS configurés ;
- produits, BoM cocktails, stock et réapprovisionnement gérés ;
- commande QR et espace barman OWL ;
- planning OWL avec génération automatique documentée ;
- journal IA complet et structuré.
