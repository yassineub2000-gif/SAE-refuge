from datetime import timedelta

from odoo import api, fields, models


class RefugeShift(models.Model):
    """Créneau de travail attribué à un employé sur une date donnée.

    Produit par l'algorithme de génération (refuge.planning.generator) puis
    éventuellement édité manuellement dans l'interface OWL.
    """

    _name = "refuge.planning.shift"
    _description = "Shift (créneau de travail)"
    _order = "date, start_time, employee_id"

    employee_id = fields.Many2one(
        "hr.employee", string="Employé", required=True, ondelete="cascade", index=True,
    )
    date = fields.Date(string="Date", required=True, index=True)
    start_time = fields.Float(
        string="Heure début", required=True,
        help="Format flottant Odoo : 10.0 = 10h00, 18.5 = 18h30.",
    )
    end_time = fields.Float(
        string="Heure fin", required=True,
        help="Peut être inférieure à start_time si le shift passe minuit "
             "(ex : start=18, end=1.0 pour un service de 18h à 01h). "
             "La durée utilise alors le modulo 24h.",
    )
    duration = fields.Float(
        string="Durée (h)", compute="_compute_duration", store=True,
    )
    state = fields.Selection(
        [("draft", "Proposé"), ("confirmed", "Validé"), ("cancelled", "Annulé")],
        default="draft", required=True,
    )
    is_generated = fields.Boolean(
        string="Généré automatiquement",
        help="Coché pour les shifts créés par l'algorithme de génération "
             "(par opposition aux shifts ajoutés manuellement par le gérant).",
    )
    notes = fields.Char(string="Notes")

    @api.depends("start_time", "end_time")
    def _compute_duration(self):
        for rec in self:
            if rec.end_time < rec.start_time:
                rec.duration = (24.0 - rec.start_time) + rec.end_time
            else:
                rec.duration = rec.end_time - rec.start_time

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_cancel(self):
        self.write({"state": "cancelled"})

    def action_reset_to_draft(self):
        self.write({"state": "draft"})

    @api.model
    def load_demo_planning(self):
        today = fields.Date.context_today(self)
        monday = today - timedelta(days=today.weekday())
        horizon_end = monday + timedelta(days=13)
        if self.search_count([("date", ">=", monday), ("date", "<=", horizon_end)]):
            return True

        generator = self.env["refuge.planning.generator"].create({"week_start": monday})
        result = generator.generate_week(monday)
        generated_shifts = self.browse(result.get("shift_ids", []))
        if generated_shifts:
            generated_shifts.write({"state": "confirmed"})

        employees = {
            "pierre": self.env.ref("refuge_aventuriers.emp_pierre_leblanc", raise_if_not_found=False),
            "marlene": self.env.ref("refuge_aventuriers.emp_marlene_dupont", raise_if_not_found=False),
            "anthony": self.env.ref("refuge_aventuriers.emp_anthony_faure", raise_if_not_found=False),
        }
        demo_shifts = [
            (employees["marlene"], monday + timedelta(days=2), 18.0, 1.0, "confirmed", False, "Service concert"),
            (employees["anthony"], monday + timedelta(days=4), 10.0, 16.0, "draft", False, "Renfort terrasse"),
            (employees["pierre"], monday + timedelta(days=5), 10.0, 14.0, "cancelled", False, "Essai planning annulé"),
        ]
        for employee, shift_date, start_time, end_time, state, is_generated, notes in demo_shifts:
            if not employee:
                continue
            existing = self.search([
                ("employee_id", "=", employee.id),
                ("date", "=", shift_date),
                ("start_time", "=", start_time),
                ("end_time", "=", end_time),
            ], limit=1)
            if existing:
                continue
            self.create({
                "employee_id": employee.id,
                "date": shift_date,
                "start_time": start_time,
                "end_time": end_time,
                "state": state,
                "is_generated": is_generated,
                "notes": notes,
            })
        return True
