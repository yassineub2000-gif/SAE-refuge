from odoo import api, fields, models


class PosOrder(models.Model):
    _inherit = "pos.order"

    def _check_existing_loyalty_cards(self, coupon_data):
        partner_ids = [
            int(vals.get("partner_id"))
            for vals in coupon_data.values()
            if vals.get("partner_id")
        ]
        if partner_ids:
            self.env["loyalty.card"].sudo().search([
                ("partner_id", "in", partner_ids),
                ("program_type", "=", "loyalty"),
            ]).refuge_expire_if_needed()
        return super()._check_existing_loyalty_cards(coupon_data)

    @api.model
    def create_from_ui(self, orders, draft=False):
        order_ids = super().create_from_ui(orders, draft=draft)
        if draft or not order_ids:
            return order_ids
        self.browse(order_ids).filtered("partner_id").mapped("partner_id").write({
            "refuge_last_order_date": fields.Date.context_today(self),
        })
        return order_ids
