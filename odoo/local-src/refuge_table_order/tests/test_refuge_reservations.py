from datetime import timedelta

from odoo import fields
from odoo.tests.common import TransactionCase


class TestRefugeReservations(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Reservation = cls.env["refuge.table.reservation"]

    def test_demo_reservations_exist_for_next_week(self):
        now = fields.Datetime.to_datetime(fields.Datetime.now())
        reservations = self.Reservation.search([
            ("reservation_datetime", ">=", now),
            ("reservation_datetime", "<=", now + timedelta(days=7)),
        ])
        self.assertTrue(reservations, "Des réservations de démonstration doivent être présentes.")
        self.assertTrue(
            set(reservations.mapped("status")).issubset({"confirmed", "seated"}),
            "Les réservations de démo doivent rester dans des statuts actifs cohérents.",
        )
        self.assertTrue(all(name.startswith("RES-") for name in reservations.mapped("name")))

    def test_create_reservation_prefills_phone_and_reference(self):
        partner = self.env.ref("refuge_aventuriers.partner_cli_jean_martin")
        table = self.env.ref("refuge_table_order.table_1")
        reservation = self.Reservation.create({
            "partner_id": partner.id,
            "table_id": table.id,
            "reservation_datetime": fields.Datetime.to_datetime(fields.Datetime.now()) + timedelta(days=10),
            "party_size": 3,
        })
        self.assertEqual(reservation.phone, partner.phone)
        self.assertTrue(reservation.name.startswith("RES-"))
