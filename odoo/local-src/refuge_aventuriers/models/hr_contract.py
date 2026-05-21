from odoo import fields, models


class HrContract(models.Model):
    """Contrat de travail. On y porte explicitement les heures contractuelles
    hebdomadaires : c'est la source de vérité utilisée par le générateur de
    planning (cf. refuge_planning)."""

    _inherit = "hr.contract"

    refuge_weekly_hours = fields.Float(
        string="Heures contractuelles / semaine",
        default=24.0,
        help="Volume horaire contractuel hebdomadaire (24h pour les CDI temps "
             "partiel du Refuge). Utilisé par la génération de planning.",
    )
