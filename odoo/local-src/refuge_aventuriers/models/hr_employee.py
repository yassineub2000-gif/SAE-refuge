from odoo import api, fields, models


# Spec officielle des 4 employés (fichier client, corrigée par le gérant) :
# - Corentin Leblanc remplace le "Pierre Leblanc" du jeu initial.
# - 24h contractuelles hebdomadaires pour tous (correction du 20h du sujet).
# Cette table sert d'idempotence : appliquée à chaque mise à jour du module.
_REFUGE_STAFF_SPEC = {
    "emp_pierre_leblanc": {  # xmlid conservé, identité rectifiée
        "name": "Corentin Leblanc",
        "work_email": "corentin.leblanc@refuge-aventuriers.fr",
        "job_title": "Barman",
        "refuge_available_days": "Mar, Mer, Jeu, Ven, Sam",
        "refuge_hour_preference": "10h–18h",
    },
    "emp_marlene_dupont": {
        "name": "Marlène Dupont",
        "work_email": "marlene.dupont@refuge-aventuriers.fr",
        "job_title": "Barmaid",
        "refuge_available_days": "Mer, Jeu, Ven, Sam, Dim",
        "refuge_hour_preference": "18h–01h",
    },
    "emp_anthony_faure": {
        "name": "Anthony Faure",
        "work_email": "anthony.faure@refuge-aventuriers.fr",
        "job_title": "Barman",
        "refuge_available_days": "Mar, Jeu, Ven, Sam, Dim",
        "refuge_hour_preference": "Flexible",
    },
    "emp_julie_perrin": {
        "name": "Julie Perrin",
        "work_email": "julie.perrin@refuge-aventuriers.fr",
        "job_title": "Barmaid",
        "refuge_available_days": "Mer, Ven, Sam, Dim",
        "refuge_hour_preference": "Après 16h",
    },
}


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def _refuge_link_staff_users(self):
        """Rattache chaque employé à l'utilisateur de même email.

        Idempotent : appelé via <function> dans data/refuge_staff_users.xml à
        chaque mise à jour du module (les fiches hr.employee sont en
        noupdate=1, on ne peut donc pas poser user_id par <record>)."""
        for emp in self.search([("work_email", "!=", False),
                                ("user_id", "=", False)]):
            user = self.env["res.users"].search(
                [("login", "=", emp.work_email)], limit=1)
            if user:
                emp.user_id = user.id

    @api.model
    def _refuge_sync_contract_hours(self):
        """Aligne les fiches employé sur la spec officielle (idempotent — appelé
        via <function> car hr_employee.xml est en noupdate=1) :
          - identité (nom, email, poste, jours dispo, préférence horaire),
          - 24h contractuelles + calendrier « Refuge — 24h/sem »."""
        calendar = self.env.ref(
            "refuge_aventuriers.resource_calendar_refuge_24h",
            raise_if_not_found=False)
        for xmlid, spec in _REFUGE_STAFF_SPEC.items():
            emp = self.env.ref(
                "refuge_aventuriers." + xmlid, raise_if_not_found=False)
            if not emp:
                continue
            vals = dict(spec)
            vals["refuge_weekly_hours"] = 24.0
            if calendar:
                vals["resource_calendar_id"] = calendar.id
            emp.write(vals)

    refuge_weekly_hours = fields.Float(
        string="Heures contractuelles / semaine",
        help="Volume horaire contractuel (24h pour les CDI temps partiel du "
             "Refuge). Reflète le contrat hr.contract lié.",
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
