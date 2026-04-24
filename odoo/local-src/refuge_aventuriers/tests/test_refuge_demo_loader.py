from odoo.tests.common import TransactionCase


class TestRefugeDemoLoader(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.loader = cls.env["refuge.demo.loader"]
        cls.program = cls.env.ref("refuge_aventuriers.loyalty_refuge_program")
        cls.partner_active = cls.env.ref("refuge_aventuriers.partner_cli_jean_martin")
        cls.partner_expired = cls.env.ref("refuge_aventuriers.partner_cli_marc_leroy")
        cls.product = cls.env.ref("refuge_aventuriers.prod_vitus_50_cl")
        cls.location = cls.env.ref("stock.stock_location_stock")

    def test_demo_loader_creates_stock_and_orderpoint(self):
        orderpoint = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", self.product.id),
            ("location_id", "=", self.location.id),
        ], limit=1)
        self.assertTrue(orderpoint, "Le stock mini doit créer une règle de réapprovisionnement.")
        self.assertGreater(orderpoint.product_min_qty, 0)

        quantity = self.env["stock.quant"]._get_available_quantity(self.product, self.location)
        self.assertGreater(quantity, 0, "Le produit de démonstration doit avoir du stock.")

    def test_demo_loader_handles_loyalty_activity_and_expiration(self):
        active_card = self.env["loyalty.card"].search([
            ("program_id", "=", self.program.id),
            ("partner_id", "=", self.partner_active.id),
        ], limit=1)
        expired_card = self.env["loyalty.card"].search([
            ("program_id", "=", self.program.id),
            ("partner_id", "=", self.partner_expired.id),
        ], limit=1)

        self.assertTrue(active_card, "Une carte fidélité doit être créée pour le client actif.")
        self.assertTrue(expired_card, "Une carte fidélité doit être créée pour le client inactif.")
        self.assertFalse(self.partner_active.refuge_loyalty_expired)
        self.assertTrue(self.partner_expired.refuge_loyalty_expired)
        self.assertGreater(active_card.points, 0)
        self.assertEqual(
            expired_card.points,
            0,
            "Les points du client inactif depuis plus de 6 mois doivent être expirés.",
        )

    def test_demo_loader_assigns_images_to_all_products(self):
        product_refs = [
            self.env.ref(f"refuge_aventuriers.{product_data['id']}")
            for product_data in self.loader._load_raw_data()["products"]
        ]
        self.assertTrue(all(product.image_1920 for product in product_refs))

    def test_expired_loyalty_helper_is_idempotent(self):
        expired_card = self.env["loyalty.card"].search([
            ("program_id", "=", self.program.id),
            ("partner_id", "=", self.partner_expired.id),
        ], limit=1)
        self.assertTrue(expired_card.refuge_is_expired())
        expired_card.refuge_expire_if_needed()
        self.assertEqual(expired_card.points, 0)
