from odoo import fields, models

# Représentation du tableau de disponibilités du fichier Excel fourni
# (feuille « Disponibilités Planning »).
# 0 = Lundi … 6 = Dimanche — conforme à la convention Python datetime.weekday().

WEEKDAYS = [
    ("0", "Lundi"),
    ("1", "Mardi"),
    ("2", "Mercredi"),
    ("3", "Jeudi"),
    ("4", "Vendredi"),
    ("5", "Samedi"),
    ("6", "Dimanche"),
]

AVAILABILITY = [
    ("available", "Disponible"),
    ("on_request", "Sur demande"),
    ("unavailable", "Indisponible"),
]


class RefugeAvailability(models.Model):
    """Disponibilité hebdomadaire d'un employé pour un jour donné.

    Sert d'entrée à l'algorithme de génération automatique du planning.
    Le fichier Excel fourni par le client est importé lors de l'installation
    du module (data/refuge_availability_data.xml).
    """

    _name = "refuge.planning.availability"
    _description = "Disponibilité employé (hebdo)"
    _rec_name = "employee_id"
    _order = "employee_id, weekday"

    employee_id = fields.Many2one(
        "hr.employee", string="Employé", required=True, ondelete="cascade", index=True,
    )
    weekday = fields.Selection(WEEKDAYS, string="Jour", required=True)
    status = fields.Selection(
        AVAILABILITY, string="Disponibilité", required=True, default="available",
    )
    hour_preference = fields.Selection(
        [("morning", "Matin (10h-18h)"),
         ("evening", "Soir (18h-01h)"),
         ("flexible", "Flexible")],
        string="Préférence horaire",
        default="flexible",
    )

    _sql_constraints = [
        ("employee_weekday_unique",
         "unique(employee_id, weekday)",
         "Une seule ligne de disponibilité par employé et par jour."),
    ]
