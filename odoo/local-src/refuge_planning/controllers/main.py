"""Routes de l'application OWL Planning.

Une page standalone qui sert le bundle OWL + des endpoints JSON-RPC pour
lire/écrire les disponibilités et déclencher la génération.
"""

from datetime import date, timedelta

from odoo import fields, http
from odoo.http import request


class RefugePlanningController(http.Controller):

    @http.route("/refuge/planning", type="http", auth="user")
    def planning_page(self, **kw):
        return request.render("refuge_planning.planning_page", {})

    # -------------------------------------------------------------------- JSON-RPC

    @http.route("/refuge/api/planning/state", type="json", auth="user")
    def api_state(self, week_start=None, **kw):
        if week_start:
            monday = date.fromisoformat(week_start)
        else:
            monday = date.today() - timedelta(days=date.today().weekday())

        employees = request.env["hr.employee"].search([], order="name")
        avails = request.env["refuge.planning.availability"].search([])
        shifts = request.env["refuge.planning.shift"].search([
            ("date", ">=", monday), ("date", "<=", monday + timedelta(days=6)),
        ])
        return {
            "week_start": monday.isoformat(),
            "employees": [
                {"id": e.id, "name": e.display_name,
                 "weekly_hours": e.refuge_weekly_hours or 20.0,
                 "preference": e.refuge_hour_preference or ""}
                for e in employees
            ],
            "availabilities": [
                {"id": a.id, "employee_id": a.employee_id.id,
                 "weekday": int(a.weekday), "status": a.status,
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
    def api_set_availability(self, employee_id, weekday, status, hour_preference="flexible", **kw):
        Avail = request.env["refuge.planning.availability"]
        existing = Avail.search([("employee_id", "=", int(employee_id)),
                                 ("weekday", "=", str(weekday))], limit=1)
        vals = {"employee_id": int(employee_id), "weekday": str(weekday),
                "status": status, "hour_preference": hour_preference}
        if existing:
            existing.write(vals)
            return {"ok": True, "id": existing.id}
        rec = Avail.create(vals)
        return {"ok": True, "id": rec.id}

    @http.route("/refuge/api/planning/set_employee_preference", type="json", auth="user")
    def api_set_employee_preference(self, employee_id, hour_preference="flexible", **kw):
        avails = request.env["refuge.planning.availability"].search([
            ("employee_id", "=", int(employee_id)),
        ])
        avails.write({"hour_preference": hour_preference})
        return {"ok": True, "updated": len(avails)}

    @http.route("/refuge/api/planning/create_shift", type="json", auth="user")
    def api_create_shift(self, employee_id, date, start_time, end_time, notes="", state="confirmed", **kw):
        shift_date = fields.Date.to_date(date)
        if shift_date.weekday() == 0:
            return {"error": "closed_monday"}
        if state not in ("draft", "confirmed", "cancelled"):
            return {"error": "invalid_state"}
        employee = request.env["hr.employee"].browse(int(employee_id)).exists()
        if not employee:
            return {"error": "employee_not_found"}
        shift = request.env["refuge.planning.shift"].create({
            "employee_id": employee.id,
            "date": shift_date,
            "start_time": float(start_time),
            "end_time": float(end_time),
            "state": state,
            "is_generated": False,
            "notes": notes or False,
        })
        return {"ok": True, "id": shift.id}

    @http.route("/refuge/api/planning/generate", type="json", auth="user")
    def api_generate(self, week_start, **kw):
        monday = date.fromisoformat(week_start)
        gen = request.env["refuge.planning.generator"].create({"week_start": monday})
        result = gen.generate_week(monday)
        return {"ok": True, **result}

    @http.route("/refuge/api/planning/set_shift_state", type="json", auth="user")
    def api_set_shift_state(self, shift_id, state, **kw):
        if state not in ("draft", "confirmed", "cancelled"):
            return {"error": "invalid_state"}
        shift = request.env["refuge.planning.shift"].browse(int(shift_id)).exists()
        if not shift:
            return {"error": "shift_not_found"}
        shift.write({"state": state})
        return {"ok": True}

    @http.route("/refuge/api/planning/delete_shift", type="json", auth="user")
    def api_delete_shift(self, shift_id, **kw):
        shift = request.env["refuge.planning.shift"].browse(int(shift_id)).exists()
        if not shift:
            return {"error": "shift_not_found"}
        shift.unlink()
        return {"ok": True}
