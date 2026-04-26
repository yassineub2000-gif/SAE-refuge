import base64
import json
from pathlib import Path

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class ProductTemplate(models.Model):
    _inherit = "product.template"

    refuge_is_cocktail = fields.Boolean(
        string="Cocktail / Verre composé",
        help="Marque les produits dont la vente déclenche automatiquement la décrémentation "
             "des ingrédients via une nomenclature de type kit (phantom BoM).",
    )
    refuge_unit_cost = fields.Float(
        string="Coût de revient (calculé)",
        compute="_compute_refuge_unit_cost",
        digits="Product Price",
        help="Somme des coûts standards des composants de la nomenclature kit/phantom, "
             "pondérée par les quantités. Sert à valider la marge cocktail.",
    )
    refuge_unit_margin = fields.Float(
        string="Marge unitaire",
        compute="_compute_refuge_unit_cost",
        digits="Product Price",
        help="Différence entre le prix de vente HT et le coût de revient calculé.",
    )
    refuge_stock_alert = fields.Boolean(
        string="Alerte stock minimum",
        compute="_compute_refuge_stock_alert",
        search="_search_refuge_stock_alert",
        help="Vrai si la quantité disponible est sous le seuil minimum défini "
             "par une règle de réapprovisionnement (orderpoint).",
    )

    @api.depends("qty_available", "product_variant_ids.qty_available")
    def _compute_refuge_stock_alert(self):
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        op_by_product = {}
        ops = Orderpoint.search([("product_id", "in", self.product_variant_ids.ids)])
        for op in ops:
            op_by_product.setdefault(op.product_id.id, []).append(op.product_min_qty)
        for tmpl in self:
            min_qty = 0.0
            for variant in tmpl.product_variant_ids:
                mins = op_by_product.get(variant.id) or []
                if mins:
                    min_qty = max(min_qty, max(mins))
            tmpl.refuge_stock_alert = bool(min_qty) and (tmpl.qty_available or 0.0) < min_qty

    def _search_refuge_stock_alert(self, operator, value):
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        alert_ids = set()
        for op in Orderpoint.search([("product_min_qty", ">", 0)]):
            tmpl = op.product_id.product_tmpl_id
            if (tmpl.qty_available or 0.0) < op.product_min_qty:
                alert_ids.add(tmpl.id)
        wants_alert = (operator == "=" and bool(value)) or (operator == "!=" and not value)
        return [("id", "in" if wants_alert else "not in", list(alert_ids))]

    @api.depends("bom_ids", "bom_ids.bom_line_ids", "bom_ids.bom_line_ids.product_qty",
                 "bom_ids.bom_line_ids.product_id.standard_price", "list_price", "standard_price")
    def _compute_refuge_unit_cost(self):
        Bom = self.env["mrp.bom"].sudo()
        for tmpl in self:
            bom = Bom._bom_find(tmpl.product_variant_id, bom_type="phantom").get(tmpl.product_variant_id) \
                if tmpl.product_variant_id else False
            if bom:
                cost = sum(
                    (line.product_id.standard_price or 0.0) * line.product_qty
                    for line in bom.bom_line_ids
                )
            else:
                cost = tmpl.standard_price or 0.0
            tmpl.refuge_unit_cost = cost
            tmpl.refuge_unit_margin = (tmpl.list_price or 0.0) - cost

    def action_refuge_refresh_image(self):
        """Recharge l'image produit :
        1) si un fichier `<xmlid>.{jpg|png|webp}` existe dans
           `static/src/img/products/`, il **écrase** l'image courante,
        2) sinon, on régénère le placeholder SVG via le demo loader,
        3) les images uploadées manuellement (sans fichier statique)
           restent inchangées par ce bouton.
        """
        Loader = self.env["refuge.demo.loader"].sudo()
        raw_data_path = (
            Path(__file__).resolve().parent.parent / "data" / "_raw_data.json"
        )
        if not raw_data_path.exists():
            raise UserError(_("Fichier _raw_data.json introuvable."))
        raw_data = json.loads(raw_data_path.read_text(encoding="utf-8"))
        by_xid = {f"refuge_aventuriers.{p['id']}": p for p in raw_data.get("products", [])}
        refreshed = 0
        for template in self:
            variant = template.product_variant_id
            if not variant:
                continue
            xid = variant.get_external_id().get(variant.id)
            product_data = by_xid.get(xid)
            if not product_data:
                continue
            image_path = Loader._get_product_image_path(product_data["id"])
            if image_path:
                template.image_1920 = base64.b64encode(image_path.read_bytes())
                refreshed += 1
                continue
            svg = Loader._product_image_svg(product_data)
            template.image_1920 = base64.b64encode(svg.encode("utf-8"))
            refreshed += 1
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Images produit"),
                "message": _("%s image(s) rafraîchie(s).") % refreshed,
                "type": "success",
            },
        }
