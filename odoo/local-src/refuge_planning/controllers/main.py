"""Routes de l'application OWL Planning.

Une page standalone qui sert le bundle OWL + des endpoints JSON-RPC pour
consulter les disponibilités et piloter le planning.
"""

from datetime import date, timedelta

from odoo import fields, http
from odoo.http import request


class RefugePlanningController(http.Controller):

    @http.route("/refuge/planning", type="http", auth="user")
    def planning_page(self, **kw):
        return request.render("refuge_planning.planning_page", {})

    # -------------------------------------------------------------------- JSON-RPC

    def _own_employee(self):
        """Employé rattaché à l'utilisateur connecté (ou empty recordset)."""
        return request.env["hr.employee"].sudo().search(
            [("user_id", "=", request.env.user.id)], limit=1)

    def _is_admin(self):
        u = request.env.user
        if u._is_admin() or u._is_system():
            return True
        # Compte gérant / RH : pas forcément superadmin, mais habilité à piloter
        # le planning s'il n'est pas une fiche employé tablette.
        return (
            u.has_group("hr.group_hr_user")
            and not self._own_employee()
        )

    def _bar_employees(self):
        return request.env["hr.employee"].sudo().search(
            [("work_email", "ilike", "refuge-aventuriers.fr")], order="name"
        )

    def _check_can_edit_employee(self, employee_id):
        """Le gérant édite les disponibilités de tout le monde ; un employé
        ne peut éditer que sa propre ligne."""
        if self._is_admin():
            return True
        own = self._own_employee()
        return bool(own) and own.id == int(employee_id)

    @http.route("/refuge/api/planning/state", type="json", auth="user")
    def api_state(self, week_start=None, **kw):
        if week_start:
            monday = date.fromisoformat(week_start)
        else:
            monday = date.today() - timedelta(days=date.today().weekday())

        employees = self._bar_employees()
        avails = request.env["refuge.planning.availability"].search([
            ("employee_id", "in", employees.ids),
        ])
        shifts = request.env["refuge.planning.shift"].search([
            ("employee_id", "in", employees.ids),
            ("date", ">=", monday), ("date", "<=", monday + timedelta(days=6)),
        ])
        own = self._own_employee()
        return {
            "week_start": monday.isoformat(),
            "own_employee_id": own.id or False,
            "is_admin": self._is_admin(),
            "employees": [
                {"id": e.id, "name": e.display_name,
                 "weekly_hours": e.refuge_weekly_hours or 24.0,
                 "preference": e.refuge_hour_preference or ""}
                for e in employees
            ],
            "availabilities": [
                {"id": a.id, "employee_id": a.employee_id.id,
                 "weekday": int(a.weekday), "status": a.status,
                 "pref_start": a.pref_start, "pref_end": a.pref_end,
                 "slot_mask": a.slot_mask or ("0" * 30),
                 "hour_preference": a.hour_preference}
                for a in avails
            ],
            "shifts": [
                {"id": s.id, "employee_id": s.employee_id.id,
                 "employee_name": s.employee_id.display_name,
                 "date": s.date.isoformat(),
                 "start_time": s.start_time, "end_time": s.end_time,
                 "duration": s.duration, "state": s.state,
                 "is_generated": s.is_generated,
                 "notes": s.notes or ""}
                for s in shifts
            ],
        }

    @http.route("/refuge/api/planning/set_availability", type="json", auth="user")
    def api_set_availability(self, employee_id, weekday, status,
                             pref_start=None, pref_end=None,
                             hour_preference=None, **kw):
        if not self._check_can_edit_employee(employee_id):
            return {"error": "not_allowed"}
        Avail = request.env["refuge.planning.availability"].sudo()
        existing = Avail.search([("employee_id", "=", int(employee_id)),
                                 ("weekday", "=", str(weekday))], limit=1)
        vals = {"employee_id": int(employee_id), "weekday": str(weekday),
                "status": status}
        if pref_start is not None:
            vals["pref_start"] = float(pref_start)
        if pref_end is not None:
            vals["pref_end"] = float(pref_end)
        if hour_preference is not None:
            vals["hour_preference"] = hour_preference
        if existing:
            existing.write(vals)
            return {"ok": True, "id": existing.id}
        rec = Avail.create(vals)
        return {"ok": True, "id": rec.id}

    @http.route("/refuge/api/planning/set_mask", type="json", auth="user")
    def api_set_mask(self, employee_id, weekday, mask, status=None, **kw):
        """Met à jour le masque demi-heure d'un (employé, jour). Status
        dérivé : 'available' si au moins un slot, sinon 'unavailable'."""
        if not self._check_can_edit_employee(employee_id):
            return {"error": "not_allowed"}
        if not isinstance(mask, str) or len(mask) != 30 \
                or any(c not in "01" for c in mask):
            return {"error": "invalid_mask"}
        Avail = request.env["refuge.planning.availability"].sudo()
        existing = Avail.search([("employee_id", "=", int(employee_id)),
                                 ("weekday", "=", str(weekday))], limit=1)
        if "1" not in mask:
            final_status = "unavailable"
        elif status == "available":
            final_status = status
        else:
            final_status = "available"
        vals = {
            "employee_id": int(employee_id), "weekday": str(weekday),
            "slot_mask": mask, "status": final_status,
        }
        if existing:
            existing.write(vals)
            return {"ok": True, "id": existing.id}
        rec = Avail.create(vals)
        return {"ok": True, "id": rec.id}

    @http.route("/refuge/api/planning/set_employee_preference", type="json", auth="user")
    def api_set_employee_preference(self, employee_id, hour_preference="flexible", **kw):
        if not self._check_can_edit_employee(employee_id):
            return {"error": "not_allowed"}
        avails = request.env["refuge.planning.availability"].search([
            ("employee_id", "=", int(employee_id)),
        ])
        avails.write({"hour_preference": hour_preference})
        return {"ok": True, "updated": len(avails)}

    @http.route("/refuge/api/planning/reset_default", type="json", auth="user")
    def api_reset_default(self, employee_id=None, **kw):
        """Réinitialise les disponibilités d'un employé (ou de tous si
        employee_id est absent) à la spec officielle. Restreint à son
        propre employé pour les non-admin."""
        Avail = request.env["refuge.planning.availability"].sudo()
        if employee_id:
            if not self._check_can_edit_employee(employee_id):
                return {"error": "not_allowed"}
            emp = request.env["hr.employee"].sudo().browse(int(employee_id)).exists()
            if not emp:
                return {"error": "not_found"}
            data = request.env["ir.model.data"].sudo().search(
                [("model", "=", "hr.employee"), ("res_id", "=", emp.id)], limit=1)
            xmlid = f"{data.module}.{data.name}" if data else None
            if not xmlid:
                return {"error": "no_xmlid_for_employee"}
            Avail._refuge_set_defaults(employee_xmlid=xmlid)
        else:
            # Reset global réservé à l'admin (changement sensible).
            if not self._is_admin():
                return {"error": "not_allowed"}
            Avail._refuge_set_defaults()
        return {"ok": True}

    @http.route("/refuge/api/planning/create_shift", type="json", auth="user")
    def api_create_shift(self, employee_id, date, start_time, end_time, notes="", state="confirmed", **kw):
        if not self._is_admin():
            return {"error": "not_allowed"}
        shift_date = fields.Date.to_date(date)
        if shift_date.weekday() == 0:
            return {"error": "closed_monday"}
        if state not in ("draft", "confirmed", "cancelled"):
            return {"error": "invalid_state"}
        employee = request.env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return {"error": "employee_not_found"}
        shift = request.env["refuge.planning.shift"].sudo().create({
            "employee_id": employee.id,
            "date": shift_date,
            "start_time": float(start_time),
            "end_time": float(end_time),
            "state": state,
            "is_generated": False,
            "notes": notes or False,
        })
        return {"ok": True, "id": shift.id}

    @http.route("/refuge/api/planning/update_shift", type="json", auth="user")
    def api_update_shift(self, shift_id, employee_id, date, start_time, end_time, notes="", state="draft", **kw):
        if not self._is_admin():
            return {"error": "not_allowed"}
        shift = request.env["refuge.planning.shift"].sudo().browse(int(shift_id)).exists()
        if not shift:
            return {"error": "shift_not_found"}
        shift.write({
            "employee_id": int(employee_id),
            "date": fields.Date.to_date(date),
            "start_time": float(start_time),
            "end_time": float(end_time),
            "state": state,
            "notes": notes or False,
        })
        return {"ok": True}

    @http.route("/refuge/api/planning/generate", type="json", auth="user")
    def api_generate(self, week_start, **kw):
        # Génération globale : action sensible — réservée à l'admin.
        if not self._is_admin():
            return {"error": "not_allowed"}
        monday = date.fromisoformat(week_start)
        gen = request.env["refuge.planning.generator"].sudo().create({"week_start": monday})
        result = gen.generate_week(monday)
        return {"ok": True, **result}

    @http.route("/refuge/api/planning/validate_week", type="json", auth="user")
    def api_validate_week(self, week_start, **kw):
        """Passe tous les shifts ``draft`` de la semaine en ``confirmed``.
        Action gérant : c'est l'étape « validation manuelle du planning
        proposé » (cf. cahier des charges)."""
        if not self._is_admin():
            return {"error": "not_allowed"}
        monday = date.fromisoformat(week_start)
        drafts = request.env["refuge.planning.shift"].sudo().search([
            ("date", ">=", monday),
            ("date", "<=", monday + timedelta(days=6)),
            ("state", "=", "draft"),
        ])
        n = len(drafts)
        drafts.write({"state": "confirmed"})
        return {"ok": True, "validated": n}

    @http.route("/refuge/api/planning/set_shift_state", type="json", auth="user")
    def api_set_shift_state(self, shift_id, state, **kw):
        if state not in ("draft", "confirmed", "cancelled"):
            return {"error": "invalid_state"}
        shift = request.env["refuge.planning.shift"].sudo().browse(int(shift_id)).exists()
        if not shift:
            return {"error": "shift_not_found"}
        if not self._is_admin():
            return {"error": "not_allowed"}
        shift.write({"state": state})
        return {"ok": True}

    @http.route("/refuge/api/planning/delete_shift", type="json", auth="user")
    def api_delete_shift(self, shift_id, **kw):
        shift = request.env["refuge.planning.shift"].sudo().browse(int(shift_id)).exists()
        if not shift:
            return {"error": "shift_not_found"}
        if not self._is_admin():
            return {"error": "not_allowed"}
        shift.unlink()
        return {"ok": True}
