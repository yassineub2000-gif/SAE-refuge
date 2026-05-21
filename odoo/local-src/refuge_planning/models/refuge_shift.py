from datetime import timedelta

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


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

    @api.model
    def _normalized_end_time(self, start_time, end_time):
        start_time = float(start_time)
        end_time = float(end_time)
        return end_time if end_time >= start_time else end_time + 24.0

    def _absolute_bounds(self):
        self.ensure_one()
        start_dt = fields.Datetime.to_datetime(self.date) + timedelta(hours=self.start_time)
        absolute_end = self._normalized_end_time(self.start_time, self.end_time)
        end_dt = fields.Datetime.to_datetime(self.date) + timedelta(hours=absolute_end)
        return start_dt, end_dt

    def _employee_weekly_limit(self):
        self.ensure_one()
        contract = self.employee_id.contract_id
        if contract and contract.refuge_weekly_hours:
            return contract.refuge_weekly_hours
        return self.employee_id.refuge_weekly_hours or 24.0

    @api.constrains("date", "start_time", "end_time", "employee_id", "state")
    def _check_refuge_constraints(self):
        for shift in self:
            if not shift.employee_id or not shift.date:
                continue
            if shift.date.weekday() == 0:
                raise ValidationError(_("Aucun shift n'est autorisé le lundi : le bar est fermé."))
            if shift.start_time < 10.0 or shift.start_time > 24.5:
                raise ValidationError(_("Les shifts doivent démarrer entre 10h00 et 00h30."))
            normalized_end = shift._normalized_end_time(shift.start_time, shift.end_time)
            if normalized_end > 25.0 or normalized_end <= 10.0:
                raise ValidationError(_("Les shifts doivent se terminer au plus tard à 01h00."))
            if any((value * 2) % 1 for value in (shift.start_time, shift.end_time)):
                raise ValidationError(_("Les shifts doivent respecter une granularité de 30 minutes."))
            if shift.duration <= 0:
                raise ValidationError(_("Un shift doit avoir une durée strictement positive."))
            if shift.duration > 10.0:
                raise ValidationError(_("La durée maximale est de 10h par jour et par employé."))

            start_dt, end_dt = shift._absolute_bounds()
            others = self.search([
                ("employee_id", "=", shift.employee_id.id),
                ("id", "!=", shift.id),
                ("state", "!=", "cancelled"),
                ("date", ">=", shift.date - timedelta(days=1)),
                ("date", "<=", shift.date + timedelta(days=1)),
            ])
            for other in others:
                other_start, other_end = other._absolute_bounds()
                if start_dt < other_end and other_start < end_dt:
                    raise ValidationError(
                        _("Ce shift chevauche déjà un autre shift de %(employee)s.", employee=shift.employee_id.name)
                    )
                rest_hours = abs((start_dt - other_end).total_seconds()) / 3600.0
                reverse_rest = abs((other_start - end_dt).total_seconds()) / 3600.0
                if other_end <= start_dt and rest_hours < 11.0:
                    raise ValidationError(_("Le repos minimum entre deux shifts est de 11h consécutives."))
                if end_dt <= other_start and reverse_rest < 11.0:
                    raise ValidationError(_("Le repos minimum entre deux shifts est de 11h consécutives."))

            week_start = shift.date - timedelta(days=shift.date.weekday())
            week_end = week_start + timedelta(days=6)
            week_shifts = self.search([
                ("employee_id", "=", shift.employee_id.id),
                ("id", "!=", shift.id),
                ("state", "!=", "cancelled"),
                ("date", ">=", week_start),
                ("date", "<=", week_end),
            ])
            total_hours = shift.duration + sum(week_shifts.mapped("duration"))
            if total_hours > shift._employee_weekly_limit() + 0.001:
                raise ValidationError(
                    _("Le volume hebdomadaire de %(employee)s dépasserait son contrat de %(hours)s h.",
                      employee=shift.employee_id.name, hours=shift._employee_weekly_limit())
                )

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
