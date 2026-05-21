import base64
import json
import math
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
        compute="_compute_refuge_stock_status",
        search="_search_refuge_stock_alert",
        help="Vrai si la quantité disponible est sous le seuil minimum défini "
             "par une règle de réapprovisionnement (orderpoint).",
    )
    refuge_stock_level = fields.Selection(
        [
            ("ok", "OK"),
            ("to_order", "À réapprovisionner"),
            ("critical", "Critique"),
            ("out", "Rupture"),
        ],
        string="Niveau stock",
        compute="_compute_refuge_stock_status",
        search="_search_refuge_stock_level",
    )
    refuge_stock_min_qty = fields.Float(
        string="Seuil minimum",
        compute="_compute_refuge_stock_limits",
        inverse="_inverse_refuge_stock_limits",
        search="_search_refuge_stock_min_qty",
        digits="Product Unit of Measure",
        help="Stock plancher à conserver. En dessous, le produit passe en alerte.",
    )
    refuge_stock_max_qty = fields.Float(
        string="Stock cible",
        compute="_compute_refuge_stock_limits",
        inverse="_inverse_refuge_stock_limits",
        digits="Product Unit of Measure",
        help="Niveau à viser au réassort pour éviter les ruptures pendant le service.",
    )
    refuge_stock_qty_multiple = fields.Float(
        string="Multiple commande",
        compute="_compute_refuge_stock_limits",
        inverse="_inverse_refuge_stock_limits",
        digits="Product Unit of Measure",
        help="Quantité de commande arrondie, alignée sur le conditionnement fournisseur.",
    )
    refuge_stock_to_order_qty = fields.Float(
        string="À commander",
        compute="_compute_refuge_stock_status",
        digits="Product Unit of Measure",
        help="Quantité recommandée pour remonter au stock cible.",
    )
    refuge_stock_coverage_ratio = fields.Float(
        string="Couverture seuil",
        compute="_compute_refuge_stock_status",
        help="Ratio entre le stock disponible et le seuil minimum.",
    )

    def _refuge_stock_location(self):
        return self.env.ref("stock.stock_location_stock", raise_if_not_found=False)

    def _refuge_stock_warehouse(self):
        location = self._refuge_stock_location()
        return (
            location.warehouse_id
            if location and location.warehouse_id
            else self.env["stock.warehouse"].sudo().search([], limit=1)
        )

    def _refuge_orderpoint_by_template(self):
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        variant_ids = self.product_variant_ids.ids
        op_by_template = {}
        if not variant_ids:
            return op_by_template
        ops = Orderpoint.search([("product_id", "in", variant_ids)], order="product_min_qty desc, id")
        for op in ops:
            tmpl = op.product_id.product_tmpl_id
            op_by_template.setdefault(tmpl.id, op)
        return op_by_template

    def _refuge_primary_variant(self):
        self.ensure_one()
        return self.product_variant_id or self.product_variant_ids[:1]

    def _refuge_get_or_create_orderpoint(self):
        self.ensure_one()
        variant = self._refuge_primary_variant()
        location = self._refuge_stock_location()
        warehouse = self._refuge_stock_warehouse()
        if not variant or not location or not warehouse:
            return self.env["stock.warehouse.orderpoint"]
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        orderpoint = Orderpoint.search([
            ("product_id", "=", variant.id),
            ("location_id", "=", location.id),
        ], limit=1)
        if orderpoint:
            return orderpoint
        vals = {
            "product_id": variant.id,
            "location_id": location.id,
            "warehouse_id": warehouse.id,
            "product_min_qty": 0.0,
            "product_max_qty": 0.0,
            "qty_multiple": 1.0,
            "trigger": "auto",
        }
        buy_route = self.env.ref("purchase_stock.route_warehouse0_buy", raise_if_not_found=False)
        if buy_route:
            vals["route_id"] = buy_route.id
        return Orderpoint.create(vals)

    @api.depends("product_variant_ids", "product_variant_ids.orderpoint_ids",
                 "product_variant_ids.orderpoint_ids.product_min_qty",
                 "product_variant_ids.orderpoint_ids.product_max_qty",
                 "product_variant_ids.orderpoint_ids.qty_multiple")
    def _compute_refuge_stock_limits(self):
        op_by_template = self._refuge_orderpoint_by_template()
        for tmpl in self:
            orderpoint = op_by_template.get(tmpl.id)
            tmpl.refuge_stock_min_qty = orderpoint.product_min_qty if orderpoint else 0.0
            tmpl.refuge_stock_max_qty = orderpoint.product_max_qty if orderpoint else 0.0
            tmpl.refuge_stock_qty_multiple = orderpoint.qty_multiple if orderpoint else 1.0

    def _inverse_refuge_stock_limits(self):
        for tmpl in self:
            orderpoint = tmpl._refuge_get_or_create_orderpoint()
            if not orderpoint:
                continue
            min_qty = max(tmpl.refuge_stock_min_qty or 0.0, 0.0)
            max_qty = max(tmpl.refuge_stock_max_qty or 0.0, min_qty)
            qty_multiple = max(tmpl.refuge_stock_qty_multiple or 1.0, 1.0)
            orderpoint.write({
                "product_min_qty": min_qty,
                "product_max_qty": max_qty,
                "qty_multiple": qty_multiple,
            })

    @api.depends("qty_available", "product_variant_ids.qty_available",
                 "refuge_stock_min_qty", "refuge_stock_max_qty",
                 "refuge_stock_qty_multiple")
    def _compute_refuge_stock_status(self):
        for tmpl in self:
            available = tmpl.qty_available or 0.0
            min_qty = tmpl.refuge_stock_min_qty or 0.0
            max_qty = max(tmpl.refuge_stock_max_qty or 0.0, min_qty)
            multiple = max(tmpl.refuge_stock_qty_multiple or 1.0, 1.0)
            shortage = max(max_qty - available, 0.0) if min_qty and available < min_qty else 0.0
            tmpl.refuge_stock_to_order_qty = (
                math.ceil(shortage / multiple) * multiple if shortage else 0.0
            )
            tmpl.refuge_stock_coverage_ratio = (available / min_qty) * 100 if min_qty else 0.0
            tmpl.refuge_stock_alert = bool(min_qty) and available < min_qty
            if min_qty and available <= 0:
                tmpl.refuge_stock_level = "out"
            elif min_qty and available < min_qty * 0.5:
                tmpl.refuge_stock_level = "critical"
            elif min_qty and available < min_qty:
                tmpl.refuge_stock_level = "to_order"
            else:
                tmpl.refuge_stock_level = "ok"

    def _search_refuge_stock_alert(self, operator, value):
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        alert_ids = set()
        for op in Orderpoint.search([("product_min_qty", ">", 0)]):
            tmpl = op.product_id.product_tmpl_id
            if (tmpl.qty_available or 0.0) < op.product_min_qty:
                alert_ids.add(tmpl.id)
        wants_alert = (operator == "=" and bool(value)) or (operator == "!=" and not value)
        return [("id", "in" if wants_alert else "not in", list(alert_ids))]

    def _search_refuge_stock_level(self, operator, value):
        if operator not in ("=", "!="):
            return [("id", "=", 0)]
        wanted = value if isinstance(value, (list, tuple, set)) else [value]
        matching = set()
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        for op in Orderpoint.search([("product_min_qty", ">", 0)]):
            tmpl = op.product_id.product_tmpl_id
            available = tmpl.qty_available or 0.0
            if available <= 0:
                level = "out"
            elif available < op.product_min_qty * 0.5:
                level = "critical"
            elif available < op.product_min_qty:
                level = "to_order"
            else:
                level = "ok"
            if level in wanted:
                matching.add(tmpl.id)
        return [("id", "in" if operator == "=" else "not in", list(matching))]

    def _search_refuge_stock_min_qty(self, operator, value):
        if operator not in ("=", "!=", ">", ">=", "<", "<="):
            return [("id", "=", 0)]
        Orderpoint = self.env["stock.warehouse.orderpoint"].sudo()
        ops = Orderpoint.search([("product_min_qty", operator, value)])
        return [("id", "in", ops.product_id.product_tmpl_id.ids)]

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
