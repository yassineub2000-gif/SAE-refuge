from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestRefugePlanningLogic(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.employee = cls.env.ref("refuge_aventuriers.emp_pierre_leblanc")
        cls.other_employee = cls.env.ref("refuge_aventuriers.emp_anthony_faure")
        cls.availability = cls.env["refuge.planning.availability"]
        cls.shift_model = cls.env["refuge.planning.shift"]
        today = fields.Date.context_today(cls.env.user)
        cls.monday = (today - timedelta(days=today.weekday())) + timedelta(days=28)
        cls.tuesday = cls.monday + timedelta(days=1)
        cls.wednesday = cls.monday + timedelta(days=2)
        cls.shift_model.search([
            ("date", ">=", cls.monday),
            ("date", "<=", cls.monday + timedelta(days=6)),
        ]).unlink()

    def test_mask_update_synchronizes_preferred_range(self):
        availability = self.availability.search([
            ("employee_id", "=", self.employee.id),
            ("weekday", "=", "1"),
        ], limit=1)
        availability.write({"slot_mask": "000011110000000000000000000000"})

        self.assertEqual(availability.pref_start, 12.0)
        self.assertEqual(availability.pref_end, 14.0)
        self.assertEqual(availability.status, "available")

    def test_shift_cannot_be_created_on_monday(self):
        with self.assertRaises(ValidationError):
            self.shift_model.create({
                "employee_id": self.employee.id,
                "date": self.monday,
                "start_time": 10.0,
                "end_time": 14.0,
            })

    def test_shift_respects_minimum_rest(self):
        self.shift_model.create({
            "employee_id": self.employee.id,
            "date": self.tuesday,
            "start_time": 18.0,
            "end_time": 1.0,
        })
        with self.assertRaises(ValidationError):
            self.shift_model.create({
                "employee_id": self.employee.id,
                "date": self.wednesday,
                "start_time": 10.0,
                "end_time": 14.0,
            })

    def test_generator_preserves_manual_shifts(self):
        manual_shift = self.shift_model.create({
            "employee_id": self.other_employee.id,
            "date": self.tuesday,
            "start_time": 10.0,
            "end_time": 14.0,
            "state": "confirmed",
            "is_generated": False,
            "notes": "Shift manager verrouillé",
        })

        result = self.env["refuge.planning.generator"].create({
            "week_start": self.monday,
        }).generate_week(self.monday)

        manual_shift.invalidate_recordset(["id"])
        self.assertTrue(manual_shift.exists())
        generated = self.shift_model.browse(result["shift_ids"])
        self.assertFalse(any(
            shift.employee_id == manual_shift.employee_id
            and shift.date == manual_shift.date
            and not (shift.end_time <= manual_shift.start_time or shift.start_time >= manual_shift.end_time)
            for shift in generated
        ))

    def test_generator_fully_covers_week_with_official_defaults(self):
        self.availability._refuge_set_defaults()

        result = self.env["refuge.planning.generator"].create({
            "week_start": self.monday,
        }).generate_week(self.monday)

        self.assertEqual(
            result["uncovered"],
            [],
            "La spec officielle doit permettre une couverture hebdomadaire complète.",
        )

    def test_generator_keeps_partial_coverage_when_full_day_is_impossible(self):
        anthony = self.env.ref("refuge_aventuriers.emp_anthony_faure")
        julie = self.env.ref("refuge_aventuriers.emp_julie_perrin")
        marlene = self.env.ref("refuge_aventuriers.emp_marlene_dupont")
        corentin = self.env.ref("refuge_aventuriers.emp_pierre_leblanc")
        self.availability._refuge_set_defaults()

        # Rend le mardi soir impossible tout en laissant le mardi matin faisable.
        self.availability.search([
            ("employee_id", "=", anthony.id),
            ("weekday", "=", "1"),
        ], limit=1).write({"slot_mask": "111111111111000000000000000000"})
        self.availability.search([
            ("employee_id", "=", julie.id),
            ("weekday", "=", "1"),
        ], limit=1).write({"status": "unavailable", "slot_mask": "0" * 30})
        self.availability.search([
            ("employee_id", "=", marlene.id),
            ("weekday", "=", "1"),
        ], limit=1).write({"status": "unavailable", "slot_mask": "0" * 30})
        self.availability.search([
            ("employee_id", "=", corentin.id),
            ("weekday", "=", "1"),
        ], limit=1).write({"slot_mask": "111111111111000000000000000000"})

        result = self.env["refuge.planning.generator"].create({
            "week_start": self.monday,
        }).generate_week(self.monday)

        uncovered_tuesday = [slot for slot in result["uncovered"] if slot.startswith(f"{self.tuesday.isoformat()} ")]
        tuesday_shifts = self.shift_model.search([
            ("date", "=", self.tuesday),
            ("state", "!=", "cancelled"),
        ])

        self.assertTrue(uncovered_tuesday, "Le mardi soir doit bien être signalé comme non couvert.")
        self.assertTrue(tuesday_shifts, "La journée ne doit pas être abandonnée entièrement si une couverture partielle est possible.")
