from odoo import models


class LoyaltyCard(models.Model):
    _inherit = "loyalty.card"

    def refuge_is_expired(self):
        self.ensure_one()
        return (
            self.program_type == "loyalty"
            and bool(self.partner_id)
            and self.partner_id._refuge_is_loyalty_expired()
        )

    def refuge_expire_if_needed(self):
        expired_cards = self.filtered(
            lambda card: card.program_type == "loyalty"
            and card.points > 0
            and card.partner_id
            and card.partner_id._refuge_is_loyalty_expired()
        )
        if expired_cards:
            expired_cards.write({"points": 0})
        return expired_cards
