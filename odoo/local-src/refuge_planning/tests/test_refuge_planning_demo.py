from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestRefugePlanningDemo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Shift = cls.env["refuge.planning.shift"]

    def test_demo_planning_populates_current_horizon(self):
        today = fields.Date.context_today(self.env.user)
        monday = today - timedelta(days=today.weekday())
        shifts = self.Shift.search([
            ("date", ">=", monday),
            ("date", "<=", monday + timedelta(days=13)),
        ])
        self.assertTrue(shifts, "Le planning de démonstration doit créer des shifts.")
        self.assertFalse(any(shift.date.weekday() == 0 for shift in shifts))
        self.assertIn("confirmed", shifts.mapped("state"))

    def test_manual_demo_shift_is_present(self):
        shift = self.Shift.search([("notes", "=", "Renfort terrasse")], limit=1)
        self.assertTrue(shift, "Le jeu de démonstration doit inclure un shift manuel.")
        self.assertFalse(shift.is_generated)
        self.assertEqual(shift.state, "draft")
