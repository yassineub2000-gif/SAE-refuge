"""Algorithme de génération automatique du planning hebdomadaire.

Granularité : **demi-heure** (30 slots de 30 min sur l'amplitude 10h → 01h).
Approche : recherche jour par jour avec backtracking sur des shifts continus,
en priorisant d'abord la couverture complète, puis la meilleure couverture
partielle lorsque les contraintes rendent une journée impossible à couvrir.
Documenté dans docs/ALGORITHME.md.

Slot 0  = 10:00-10:30   Slot 16 = 18:00-18:30
Slot 1  = 10:30-11:00   …
Slot 15 = 17:30-18:00   Slot 29 = 00:30-01:00
"""

from datetime import date, datetime, timedelta

from odoo import fields, models

SLOT_COUNT = 30                       # 30 demi-heures = 15h d'ouverture
CLOSED_WEEKDAY = 0                    # lundi fermé
MAX_SLOTS_PER_DAY = 20                # 10h × 2
MIN_REST_SLOTS = 22                   # 11h × 2
MIN_SHIFT_SLOTS = 4                   # 2h × 2 (anti-miettes)
DEFAULT_WEEKLY_SLOTS = 48             # 24h × 2 (fallback)
WEEKLY_TOLERANCE_SLOTS = 2            # +1h × 2


def _slot_to_hour(slot):
    """Convertit un index de slot (0..30) en heure flottante 10..25."""
    return 10.0 + slot / 2.0


def _slot_dt(d, slot):
    return datetime.combine(d, datetime.min.time()) \
        + timedelta(hours=_slot_to_hour(slot))


class RefugePlanningGenerator(models.TransientModel):
    """Générateur. Méthode principale ``generate_week(monday)``."""

    _name = "refuge.planning.generator"
    _description = "Générateur de planning hebdomadaire"

    week_start = fields.Date(
        string="Lundi de la semaine", required=True,
        default=lambda self: date.today() - timedelta(days=date.today().weekday()),
    )

    # ------------------------------------------------------------ public

    def action_generate(self):
        self.ensure_one()
        result = self.generate_week(self.week_start)
        message = f"Planning généré : {result['created']} shift(s) créé(s)."
        uncovered = result.get("uncovered") or []
        if uncovered:
            message += (
                f"\n⚠ {len(uncovered)} demi-heure(s) non couverte(s)."
            )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "Génération planning", "message": message,
                       "sticky": True},
        }

    def generate_week(self, monday):
        """Génère les shifts de la semaine en partant du lundi."""
        Employees = self.env["hr.employee"].sudo()
        Avail = self.env["refuge.planning.availability"].sudo()
        Shift = self.env["refuge.planning.shift"].sudo()

        # Purge des shifts auto-générés de cette semaine.
        week_end = monday + timedelta(days=6)
        Shift.search([
            ("date", ">=", monday), ("date", "<=", week_end),
            ("is_generated", "=", True),
        ]).unlink()

        # Périmètre strict : seuls les 4 employés du bar.
        employees = Employees.search([
            ("work_email", "ilike", "refuge-aventuriers.fr"),
            ("refuge_weekly_hours", ">", 0),
        ])
        if not employees:
            employees = Employees.search(
                [("work_email", "ilike", "refuge-aventuriers.fr")])

        avail_by = {
            (a.employee_id.id, int(a.weekday)): a
            for a in Avail.search([("employee_id", "in", employees.ids)])
        }

        weekly_slots = {e.id: int(round(self._employee_weekly_hours(e) * 2)) for e in employees}
        planned_slots = {e.id: 0 for e in employees}
        created_shifts = self.env["refuge.planning.shift"]

        preserved_shifts = Shift.search([
            ("date", ">=", monday), ("date", "<=", week_end),
            ("is_generated", "=", False),
            ("state", "!=", "cancelled"),
            ("employee_id", "in", employees.ids),
        ])
        preserved_by_day = {}
        for shift in preserved_shifts:
            start_slot, end_slot = self._shift_to_slots(shift)
            preserved_by_day.setdefault(shift.date, []).append((shift, start_slot, end_slot))
            planned_slots[shift.employee_id.id] += int(round((shift.duration or 0.0) * 2))
        open_days = [
            monday + timedelta(days=offset)
            for offset in range(7)
            if (monday + timedelta(days=offset)).weekday() != CLOSED_WEEKDAY
        ]
        prior_last_end = self._load_previous_shift_end(employees, monday)
        solutions, uncovered = self._solve_week(
            open_days, employees, avail_by, preserved_by_day,
            weekly_slots, planned_slots, prior_last_end,
        )

        for day, emp_id, start_s, end_s in solutions:
            start_h = _slot_to_hour(start_s)
            end_h_raw = _slot_to_hour(end_s)
            end_h_db = end_h_raw if end_h_raw < 24.0 else end_h_raw - 24.0
            created_shifts |= Shift.create({
                "employee_id": emp_id,
                "date": day,
                "start_time": float(start_h),
                "end_time": float(end_h_db),
                "state": "draft",
                "is_generated": True,
                "notes": False,
            })

        return {"created": len(created_shifts), "uncovered": uncovered, "shift_ids": created_shifts.ids}

    # ----------------------------------------------------------- helpers

    def _slot_label(self, slot):
        h = int(10 + slot // 2)
        m = (slot % 2) * 30
        if h >= 24:
            h -= 24
        return f"{h:02d}:{m:02d}"

    def _load_previous_shift_end(self, employees, monday):
        result = {emp.id: None for emp in employees}
        previous_shifts = self.env["refuge.planning.shift"].sudo().search([
            ("employee_id", "in", employees.ids),
            ("state", "!=", "cancelled"),
            ("date", ">=", monday - timedelta(days=2)),
            ("date", "<", monday),
        ], order="date desc, start_time desc")
        for shift in previous_shifts:
            if result[shift.employee_id.id] is None:
                result[shift.employee_id.id] = _slot_dt(shift.date, self._shift_to_slots(shift)[1])
        return result

    def _mask_intervals(self, mask):
        intervals = []
        start = None
        mask = (mask or "").ljust(SLOT_COUNT, "0")[:SLOT_COUNT]
        for index, char in enumerate(mask):
            if char == "1" and start is None:
                start = index
            if char == "0" and start is not None:
                intervals.append((start, index))
                start = None
        if start is not None:
            intervals.append((start, SLOT_COUNT))
        return intervals

    def _find_interval_for_slot(self, intervals, slot):
        for start, end in intervals:
            if start <= slot < end:
                return start, end
        return None

    def _solve_week(self, open_days, employees, avail_by, preserved_by_day, weekly_slots, planned_slots, last_end_by_emp, day_index=0):
        if day_index >= len(open_days):
            return [], []

        day = open_days[day_index]
        fixed_segments = preserved_by_day.get(day, [])
        candidates = self._enumerate_day_solutions(
            day, employees, avail_by, fixed_segments, weekly_slots, planned_slots, last_end_by_emp,
        )
        if not candidates:
            partial_segments, partial_uncovered_slots = self._best_partial_day_solution(
                day, employees, avail_by, fixed_segments, weekly_slots, planned_slots, last_end_by_emp,
            )
            updated_slots = dict(planned_slots)
            updated_last_end = dict(last_end_by_emp)
            for emp_id, start_s, end_s in partial_segments:
                updated_slots[emp_id] += end_s - start_s
                updated_last_end[emp_id] = _slot_dt(day, end_s)
            following, following_uncovered = self._solve_week(
                open_days, employees, avail_by, preserved_by_day,
                weekly_slots, updated_slots, updated_last_end, day_index + 1,
            )
            uncovered = [
                f"{day.isoformat()} {self._slot_label(slot)}"
                for slot in partial_uncovered_slots
            ]
            return [(day, *segment) for segment in partial_segments] + following, uncovered + following_uncovered

        best_solution = None
        best_meta = None
        for candidate in candidates:
            updated_slots = dict(planned_slots)
            updated_last_end = dict(last_end_by_emp)
            for emp_id, start_s, end_s in candidate:
                updated_slots[emp_id] += end_s - start_s
                updated_last_end[emp_id] = _slot_dt(day, end_s)
            following, uncovered = self._solve_week(
                open_days, employees, avail_by, preserved_by_day,
                weekly_slots, updated_slots, updated_last_end, day_index + 1,
            )
            remaining_capacity = sum(max(0, weekly_slots[e.id] - updated_slots[e.id]) for e in employees)
            meta = (len(uncovered), remaining_capacity)
            if best_meta is None or meta < best_meta:
                best_meta = meta
                best_solution = ([(day, *segment) for segment in candidate] + following, uncovered)
                if best_meta[0] == 0:
                    break
        return best_solution

    def _enumerate_day_solutions(self, day, employees, avail_by, fixed_segments, weekly_slots, planned_slots, last_end_by_emp):
        day_ctx = self._build_day_context(day, employees, avail_by, fixed_segments)
        solutions = []

        def recurse(slot, local_used, segments):
            if slot >= SLOT_COUNT:
                solutions.append(list(segments))
                return
            if slot in day_ctx["fixed_lookup"]:
                recurse(day_ctx["fixed_lookup"][slot][1], local_used, segments)
                return

            for emp_id, _start_s, end_s in self._day_slot_options(
                day, slot, employees, weekly_slots, planned_slots, last_end_by_emp, local_used, day_ctx,
            ):
                recurse(
                    end_s,
                    local_used | {emp_id},
                    segments + [(emp_id, slot, end_s)],
                )

        recurse(0, day_ctx["used_employees"], [])
        return solutions

    def _best_partial_day_solution(self, day, employees, avail_by, fixed_segments, weekly_slots, planned_slots, last_end_by_emp):
        day_ctx = self._build_day_context(day, employees, avail_by, fixed_segments)

        def recurse(slot, local_used):
            if slot >= SLOT_COUNT:
                return [], []
            if slot in day_ctx["fixed_lookup"]:
                return recurse(day_ctx["fixed_lookup"][slot][1], local_used)

            best = None
            for emp_id, _start_s, end_s in self._day_slot_options(
                day, slot, employees, weekly_slots, planned_slots, last_end_by_emp, local_used, day_ctx,
            ):
                tail_segments, tail_uncovered = recurse(end_s, local_used | {emp_id})
                candidate = ([(emp_id, slot, end_s)] + tail_segments, tail_uncovered)
                best = self._pick_better_partial(candidate, best)

            skipped_segments, skipped_uncovered = recurse(slot + 1, local_used)
            skipped = (skipped_segments, [slot] + skipped_uncovered)
            return self._pick_better_partial(skipped, best)

        return recurse(0, day_ctx["used_employees"])

    def _pick_better_partial(self, candidate, current):
        if current is None:
            return candidate
        candidate_segments, candidate_uncovered = candidate
        current_segments, current_uncovered = current
        candidate_meta = (
            len(candidate_uncovered),
            -sum((end_s - start_s) for _emp_id, start_s, end_s in candidate_segments),
        )
        current_meta = (
            len(current_uncovered),
            -sum((end_s - start_s) for _emp_id, start_s, end_s in current_segments),
        )
        return candidate if candidate_meta < current_meta else current

    def _build_day_context(self, day, employees, avail_by, fixed_segments):
        weekday = day.weekday()
        fixed_lookup = {}
        used_employees = set()
        for shift, start_s, end_s in fixed_segments:
            for slot in range(start_s, end_s):
                fixed_lookup[slot] = (shift.employee_id.id, end_s)
            used_employees.add(shift.employee_id.id)

        intervals_by_emp = {}
        for emp in employees:
            avail = avail_by.get((emp.id, weekday))
            intervals_by_emp[emp.id] = self._mask_intervals(avail.slot_mask if avail else "")
        next_fixed_start = {}
        fixed_starts = sorted({start_s for _shift, start_s, _end_s in fixed_segments})
        for slot in range(SLOT_COUNT + 1):
            starts = [start for start in fixed_starts if start > slot]
            next_fixed_start[slot] = starts[0] if starts else SLOT_COUNT

        return {
            "fixed_lookup": fixed_lookup,
            "used_employees": used_employees,
            "intervals_by_emp": intervals_by_emp,
            "next_fixed_start": next_fixed_start,
        }

    def _day_slot_options(self, day, slot, employees, weekly_slots, planned_slots, last_end_by_emp, local_used, day_ctx):
        options = []
        for emp in employees:
            if emp.id in local_used:
                continue
            interval = self._find_interval_for_slot(day_ctx["intervals_by_emp"][emp.id], slot)
            if not interval:
                continue
            previous_end = last_end_by_emp.get(emp.id)
            if previous_end and (_slot_dt(day, slot) - previous_end) < timedelta(hours=11):
                continue
            remaining_week = weekly_slots[emp.id] - planned_slots[emp.id]
            max_length = min(MAX_SLOTS_PER_DAY, remaining_week)
            if max_length < MIN_SHIFT_SLOTS:
                continue
            _interval_start, interval_end = interval
            max_end = min(interval_end, day_ctx["next_fixed_start"][slot], slot + max_length)
            if max_end - slot < MIN_SHIFT_SLOTS:
                continue
            boundary_candidates = {
                max_end,
                day_ctx["next_fixed_start"][slot],
                interval_end,
            }
            for other in employees:
                if other.id == emp.id:
                    continue
                for other_start, _other_end in day_ctx["intervals_by_emp"][other.id]:
                    if slot + MIN_SHIFT_SLOTS <= other_start <= max_end:
                        boundary_candidates.add(other_start)
            for end_s in sorted(
                [value for value in boundary_candidates if slot + MIN_SHIFT_SLOTS <= value <= max_end],
                reverse=True,
            ):
                options.append((emp.id, slot, end_s))
        return options

    def _shift_to_slots(self, shift):
        start_slot = max(0, int(round((shift.start_time - 10.0) * 2)))
        absolute_end = shift.end_time if shift.end_time >= shift.start_time else shift.end_time + 24.0
        end_slot = min(SLOT_COUNT, int(round((absolute_end - 10.0) * 2)))
        return start_slot, end_slot

    def _employee_weekly_hours(self, emp):
        contract = emp.contract_id
        if contract and contract.refuge_weekly_hours:
            return contract.refuge_weekly_hours
        if emp.refuge_weekly_hours:
            return emp.refuge_weekly_hours
        return DEFAULT_WEEKLY_SLOTS / 2.0
