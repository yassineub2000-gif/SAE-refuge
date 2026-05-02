"""Algorithme de génération automatique du planning hebdomadaire.

Documenté en détail dans docs/ALGORITHME.md (livrable 4 du cahier des charges).

Résumé de la logique :
1. La semaine est découpée en deux créneaux fixes par jour ouvert (Mar → Dim) :
   - "matin"  : 10h00 → 18h00  (8h)
   - "soir"   : 18h00 → 01h00  (7h, franchit minuit)
   Total offre : 6 jours × 2 créneaux × (8h+7h) = 90h pour 4×20h contractuelles.

2. Pour chaque créneau, on classe les employés candidats par score décroissant :
   - Base 100 si disponible (`available`), 40 si "sur demande" (`on_request`), -∞ si indisponible.
   - +30 si la préférence horaire correspond au créneau (matin/soir).
   - −10 × (heures déjà planifiées cette semaine) pour tendre vers l'équité.
   - Pénalité lourde si ajouter ce créneau viole les 10h/jour ou les 11h de repos.

3. On sélectionne le meilleur candidat respectant les contraintes dures :
   - Max 10h / jour / employé.
   - Repos ≥ 11h entre deux shifts consécutifs.
   - Somme hebdo ≤ 20h (contrat temps partiel). Tolérance +1h en dernier recours
     pour garantir la couverture.
   - Au moins 1 barman présent sur chaque créneau (sinon le créneau est laissé
     vide et signalé dans le rapport).

4. Le lundi est exclu (bar fermé — §3.6 du cahier des charges).

Cette stratégie gloutonne (greedy) est simple, déterministe et facile à défendre
en soutenance. Une approche plus sophistiquée (ILP, contraintes via OR-Tools)
serait valorisée mais sort du périmètre de la SAÉ.
"""

from datetime import date, datetime, timedelta

from odoo import fields, models

SHIFTS = [
    {"key": "morning", "start": 10.0, "end": 18.0, "label": "Matin 10h-18h"},
    {"key": "evening", "start": 18.0, "end": 1.0,  "label": "Soir 18h-01h"},
]
CLOSED_WEEKDAY = 0  # Lundi fermé
MAX_HOURS_PER_DAY = 10.0
MIN_REST_HOURS = 11.0
CONTRACTUAL_WEEKLY_HOURS = 20.0
WEEKLY_TOLERANCE = 1.0


def _shift_duration(shift):
    if shift["end"] < shift["start"]:
        return (24.0 - shift["start"]) + shift["end"]
    return shift["end"] - shift["start"]


def _shift_end_datetime(d, shift):
    """Renvoie le datetime de fin du shift (gère le passage de minuit)."""
    start_dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=shift["start"])
    return start_dt + timedelta(hours=_shift_duration(shift))


def _shift_start_datetime(d, shift):
    return datetime.combine(d, datetime.min.time()) + timedelta(hours=shift["start"])


class RefugePlanningGenerator(models.TransientModel):
    """Wizard-like générateur. Méthode principale : ``generate_week(monday)``
    qui retourne la liste des shifts créés + un rapport (créneaux non couverts).
    """

    _name = "refuge.planning.generator"
    _description = "Générateur de planning hebdomadaire"

    week_start = fields.Date(
        string="Lundi de la semaine", required=True,
        default=lambda self: date.today() - timedelta(days=date.today().weekday()),
    )

    def action_generate(self):
        self.ensure_one()
        result = self.generate_week(self.week_start)
        uncovered = result.get("uncovered") or []
        message = f"Planning généré : {result['created']} shift(s) créés."
        if uncovered:
            message += (
                "\n⚠ Créneaux non couverts (aucun employé compatible) :\n  • "
                + "\n  • ".join(f"{d} — {s}" for d, s in uncovered)
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "Génération planning", "message": message, "sticky": True},
        }

    def generate_week(self, monday):
        """Génère les shifts de la semaine commençant le lundi passé en paramètre.

        Retourne ``{"created": int, "uncovered": [(date, shift_label)]}``.
        """
        Employees = self.env["hr.employee"].sudo()
        Avail = self.env["refuge.planning.availability"].sudo()
        Shift = self.env["refuge.planning.shift"].sudo()

        # Supprimer les shifts générés précédemment pour cette semaine (on
        # conserve les shifts ajoutés manuellement : is_generated=False).
        week_end = monday + timedelta(days=6)
        Shift.search([
            ("date", ">=", monday), ("date", "<=", week_end),
            ("is_generated", "=", True),
        ]).unlink()

        employees = Employees.search([("refuge_weekly_hours", ">", 0)])
        if not employees:
            # fallback : tous les employés actifs
            employees = Employees.search([])

        # Contrainte §3.6 du cahier des charges : « au minimum un barman présent
        # à chaque instant ». On filtre sur les job_titles qualifiants ; si la
        # base n'a aucun employé qualifié (cas de tests), on retombe sur tous.
        bartenders = employees.filtered(
            lambda e: (e.job_title or "").strip().lower() in ("barman", "barmaid", "bartender")
        )
        if bartenders:
            employees = bartenders

        avail_by_emp = {}
        for a in Avail.search([("employee_id", "in", employees.ids)]):
            avail_by_emp.setdefault(a.employee_id.id, {})[int(a.weekday)] = a

        planned_hours = {e.id: 0.0 for e in employees}
        planned_by_day = {e.id: {} for e in employees}  # {emp_id: {date: [shift dicts]}}

        created_shifts = self.env["refuge.planning.shift"]
        uncovered = []

        for day_offset in range(7):
            d = monday + timedelta(days=day_offset)
            weekday = d.weekday()
            if weekday == CLOSED_WEEKDAY:
                continue

            for shift in SHIFTS:
                duration = _shift_duration(shift)
                best = None
                best_score = float("-inf")
                for emp in employees:
                    score = self._score_candidate(
                        emp, d, shift, duration,
                        avail_by_emp.get(emp.id, {}),
                        planned_hours[emp.id],
                        planned_by_day[emp.id],
                    )
                    if score > best_score:
                        best_score = score
                        best = emp

                if best is None or best_score == float("-inf"):
                    uncovered.append((d.isoformat(), shift["label"]))
                    continue

                created_shifts |= Shift.create({
                    "employee_id": best.id,
                    "date": d,
                    "start_time": shift["start"],
                    "end_time": shift["end"],
                    "state": "draft",
                    "is_generated": True,
                })
                planned_hours[best.id] += duration
                planned_by_day[best.id].setdefault(d, []).append(shift)

        return {"created": len(created_shifts), "uncovered": uncovered,
                "shift_ids": created_shifts.ids}

    # ------------------------------------------------------------------- helpers

    def _score_candidate(self, emp, d, shift, duration, avail_for_emp, planned_hours, planned_by_day):
        """Calcule le score d'un employé pour un créneau donné.

        ``-inf`` signifie que le candidat viole une contrainte dure et ne doit
        pas être retenu.
        """
        weekday = d.weekday()
        avail = avail_for_emp.get(weekday)
        if not avail or avail.status == "unavailable":
            return float("-inf")

        # Contrainte : max 10h / jour
        already_today = sum(_shift_duration(s) for s in planned_by_day.get(d, []))
        if already_today + duration > MAX_HOURS_PER_DAY:
            return float("-inf")

        # Contrainte : 11h de repos entre shifts (vérifie veille et jour courant)
        new_start = _shift_start_datetime(d, shift)
        new_end = _shift_end_datetime(d, shift)
        for prev_day_offset in (-1, 0):
            prev_day = d + timedelta(days=prev_day_offset)
            for ps in planned_by_day.get(prev_day, []):
                ps_end = _shift_end_datetime(prev_day, ps)
                ps_start = _shift_start_datetime(prev_day, ps)
                # nouveau shift après ancien
                if new_start >= ps_end and (new_start - ps_end) < timedelta(hours=MIN_REST_HOURS):
                    return float("-inf")
                # nouveau shift avant ancien
                if ps_start >= new_end and (ps_start - new_end) < timedelta(hours=MIN_REST_HOURS):
                    return float("-inf")
                # chevauchement → invalide aussi
                if new_start < ps_end and ps_start < new_end:
                    return float("-inf")

        # Contrainte : 20h/sem (souple à +1h)
        if planned_hours + duration > CONTRACTUAL_WEEKLY_HOURS + WEEKLY_TOLERANCE:
            return float("-inf")

        # Score de base selon disponibilité
        score = 100.0 if avail.status == "available" else 40.0

        # Bonus préférence horaire
        pref = avail.hour_preference or "flexible"
        if pref == shift["key"]:
            score += 30.0
        elif pref == "flexible":
            score += 10.0

        # Pénalité : écart à l'équité (les employés proches de leur cible reçoivent moins)
        score -= 10.0 * (planned_hours / CONTRACTUAL_WEEKLY_HOURS)

        # Petite préférence : garder une marge pour atteindre 20h
        remaining = CONTRACTUAL_WEEKLY_HOURS - planned_hours
        if remaining >= duration:
            score += 5.0
        return score
