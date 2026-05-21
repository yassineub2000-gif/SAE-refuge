import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


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
        order_results = super().create_from_ui(orders, draft=draft)
        if draft or not order_results:
            return order_results
        order_ids = []
        for result in order_results:
            if isinstance(result, dict):
                order_id = result.get("id")
            else:
                order_id = result
            if isinstance(order_id, int):
                order_ids.append(order_id)
        partners = self.browse(order_ids).filtered(lambda order: bool(order.partner_id)).mapped("partner_id")
        partners.write({
            "refuge_last_order_date": fields.Date.context_today(self),
        })
        return order_results

    def _generate_pos_order_invoice(self):
        report_service = self.env["ir.actions.report"]
        report_state = report_service.get_wkhtmltopdf_state()
        if report_state == "ok":
            return super()._generate_pos_order_invoice()

        _logger.warning(
            "[refuge_aventuriers] wkhtmltopdf state=%s, skipping server-side invoice PDF generation for POS orders %s",
            report_state,
            self.ids,
        )
        return super(PosOrder, self.with_context(generate_pdf=False))._generate_pos_order_invoice()
