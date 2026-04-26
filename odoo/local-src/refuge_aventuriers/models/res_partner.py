from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"

    refuge_loyalty_points_initial = fields.Integer(
        string="Points fidélité initiaux (import)",
        help="Solde de points de fidélité historique importé depuis l'ancien ERP EBP. "
             "Sert uniquement à initialiser la carte de fidélité lors du premier passage en caisse.",
    )
    refuge_last_order_date = fields.Date(
        string="Dernière commande",
        help="Mise à jour automatiquement par le POS. Utilisé pour déterminer l'expiration "
             "des points de fidélité (6 mois d'inactivité).",
    )
    refuge_loyalty_expired = fields.Boolean(
        string="Points fidélité expirés",
        compute="_compute_refuge_loyalty_expired",
        help="Indique si les points de fidélité doivent être considérés comme expirés "
             "après 6 mois d'inactivité.",
    )
    refuge_client_pin = fields.Char(
        string="Code client (QR)",
        size=6, copy=False,
        help="Code à 4-6 chiffres utilisé par le client pour se connecter depuis "
             "l'app OWL de commande sur table.",
    )

    def refuge_loyalty_points(self):
        """Renvoie le solde de points fidélité courant (carte la plus récente)."""
        self.ensure_one()
        if self._refuge_is_loyalty_expired():
            return 0
        card = self.env["loyalty.card"].sudo().search(
            [("partner_id", "=", self.id), ("program_type", "=", "loyalty")],
            order="create_date desc", limit=1,
        )
        return int(card.points) if card else 0

    def refuge_loyalty_card(self, create_if_missing=False):
        self.ensure_one()
        Card = self.env["loyalty.card"].sudo()
        card = Card.search(
            [("partner_id", "=", self.id), ("program_type", "=", "loyalty")],
            order="create_date desc", limit=1,
        )
        if card or not create_if_missing:
            return card
        program = self.env.ref("refuge_aventuriers.loyalty_refuge_program", raise_if_not_found=False)
        if not program:
            return Card
        return Card.create({
            "program_id": program.id,
            "partner_id": self.id,
            "points": 0,
            "code": f"REFUGE-{self.id:05d}",
        })

    @api.depends("refuge_last_order_date")
    def _compute_refuge_loyalty_expired(self):
        for partner in self:
            partner.refuge_loyalty_expired = partner._refuge_is_loyalty_expired()

    def _refuge_loyalty_cutoff_date(self):
        return fields.Date.context_today(self) - relativedelta(months=6)

    def _refuge_is_loyalty_expired(self):
        self.ensure_one()
        return bool(
            self.refuge_last_order_date
            and self.refuge_last_order_date < self._refuge_loyalty_cutoff_date()
        )
