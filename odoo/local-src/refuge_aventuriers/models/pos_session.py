from odoo import models


class PosSession(models.Model):
    _inherit = "pos.session"

    def _set_loyalty_cards(self, partners):
        partners = super()._set_loyalty_cards(partners)
        partner_records = {
            partner.id: partner
            for partner in self.env["res.partner"].browse([p["id"] for p in partners]).exists()
        }
        for partner in partners:
            partner_record = partner_records.get(partner["id"])
            if partner_record and partner_record._refuge_is_loyalty_expired():
                partner["loyalty_cards"] = {}
        return partners
