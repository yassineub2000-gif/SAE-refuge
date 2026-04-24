# Images produits — Le Refuge des Aventuriers

Ce dossier contient les **vraies photos** des produits servis au bar, affichées
dans l'application client QR (menu) et dans le POS Odoo.

## Convention de nommage

Chaque fichier doit être nommé avec le **xml id** du produit (sans le préfixe
`refuge_aventuriers.`) + une extension supportée :

```
prod_mojito.jpg
prod_margarita.png
prod_vitus_50_cl.webp
prod_taurasi_nero_ne_75cl.jpeg
```

Extensions reconnues par le loader (`refuge.demo.loader._get_product_image_path`) :
`.jpg`, `.jpeg`, `.png`, `.webp`.

La liste complète des xml ids est dans `data/_raw_data.json` (clé `id` de
chaque produit).

## Ordre de priorité

À chaque appel de `refuge.demo.loader.load_refuge_core_demo()` (ou du bouton
« Actualiser l'image » sur la fiche produit) :

1. **Fichier présent dans ce dossier** → utilisé et écrasé à chaque appel.
2. Pas de fichier, mais `product.image_1920` contient déjà une image (upload
   manuel via le backend Odoo, etc.) → **on ne touche à rien**, l'upload
   utilisateur est préservé.
3. Aucune image → un **placeholder SVG** thématique est généré (cf.
   `models/refuge_demo_loader.py`, méthode `_product_image_svg`).

## Recommandations

- **Format carré** (1:1), minimum 512×512 px. Odoo calcule les miniatures
  256×256, 128×128, etc. automatiquement.
- JPEG/WebP pour les photos, PNG pour les illustrations à fond transparent.
- Cadrage serré sur le produit, fond neutre ou cohérent avec le thème sombre
  de l'app client.

## Ajouter une image

1. Déposer le fichier ici (`prod_xxx.jpg`).
2. Déclencher la prise en compte :
   - via l'UI : fiche produit → bouton **« Actualiser l'image »**,
   - ou via le shell : `env["refuge.demo.loader"].load_refuge_core_demo()`.
3. Recharger l'app client (`Ctrl+Shift+R` pour casser le cache navigateur).
