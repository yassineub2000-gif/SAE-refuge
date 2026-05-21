from collections import defaultdict

from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _refuge_component_quantities_from_lines(self, lines):
        """Explose les cocktails POS en ingrédients stockables."""
        self.ensure_one()
        Bom = self.env["mrp.bom"].sudo()
        qty_by_product = defaultdict(float)

        for line in lines:
            product = line.product_id
            qty = abs(line.qty)
            bom = Bom._bom_find(
                product,
                company_id=line.company_id.id,
                bom_type="phantom",
            ).get(product)

            if product.product_tmpl_id.refuge_is_cocktail and bom:
                _boms, components = bom.sudo().explode(product, qty)
                for comp_line, comp_data in components:
                    component = comp_line.product_id
                    if component.type == "product":
                        qty_by_product[component.id] += comp_data["qty"]
                continue

            if product.type in ("product", "consu"):
                qty_by_product[product.id] += qty

        return qty_by_product

    def _create_move_from_pos_order_lines(self, lines):
        self.ensure_one()
        order = self.pos_order_id
        if not order or order.refuge_source != "pos":
            return super()._create_move_from_pos_order_lines(lines)

        component_qty = self._refuge_component_quantities_from_lines(lines)
        if not component_qty:
            return super()._create_move_from_pos_order_lines(lines)

        move_vals = []
        for product_id, qty in component_qty.items():
            product = self.env["product.product"].browse(product_id)
            move_vals.append({
                "name": product.display_name,
                "product_uom": product.uom_id.id,
                "picking_id": self.id,
                "picking_type_id": self.picking_type_id.id,
                "product_id": product.id,
                "product_uom_qty": qty,
                "location_id": self.location_id.id,
                "location_dest_id": self.location_dest_id.id,
                "company_id": self.company_id.id,
            })

        moves = self.env["stock.move"].create(move_vals)
        confirmed_moves = moves._action_confirm()
        confirmed_moves._add_mls_related_to_order(lines, are_qties_done=True)
        confirmed_moves.picked = True
        self._link_owner_on_return_picking(lines)
