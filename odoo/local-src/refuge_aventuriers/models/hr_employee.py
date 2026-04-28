from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    refuge_weekly_hours = fields.Float(
        string="Heures contractuelles / semaine",
        help="Volume horaire contractuel (20h pour les CDI temps partiel du Refuge).",
    )
    refuge_available_days = fields.Char(
        string="Jours disponibles",
        help="Texte libre importé depuis le fichier client (ex: 'Mar, Mer, Jeu, Ven, Sam'). "
             "La saisie structurée utilisée par l'app OWL Planning est gérée sur le modèle "
             "refuge.planning.availability.",
    )
    refuge_hour_preference = fields.Char(
        string="Préférence horaire",
        help="Créneau préféré de l'employé (ex: '10h-18h', '18h-01h', 'Flexible').",
    )
