import math
from unittest.mock import patch

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

    def test_stock_alerts_expose_actionable_replenishment_levels(self):
        template = self.product.product_tmpl_id
        orderpoint = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", self.product.id),
            ("location_id", "=", self.location.id),
        ], limit=1)
        orderpoint.write({
            "product_min_qty": 100,
            "product_max_qty": 144,
            "qty_multiple": 12,
        })

        self.assertTrue(template.refuge_stock_alert)
        self.assertEqual(template.refuge_stock_level, "critical")
        self.assertEqual(template.refuge_stock_min_qty, 100)
        self.assertEqual(template.refuge_stock_max_qty, 144)
        self.assertEqual(template.refuge_stock_to_order_qty, 96)

    def test_stock_alert_fields_update_underlying_orderpoint(self):
        template = self.product.product_tmpl_id
        orderpoint = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", self.product.id),
            ("location_id", "=", self.location.id),
        ], limit=1)

        template.write({
            "refuge_stock_min_qty": 18,
            "refuge_stock_max_qty": 54,
            "refuge_stock_qty_multiple": 6,
        })
        orderpoint.invalidate_recordset([
            "product_min_qty",
            "product_max_qty",
            "qty_multiple",
        ])

        self.assertEqual(orderpoint.product_min_qty, 18)
        self.assertEqual(orderpoint.product_max_qty, 54)
        self.assertEqual(orderpoint.qty_multiple, 6)

    def test_stock_alert_search_filters_find_critical_products(self):
        template = self.product.product_tmpl_id
        orderpoint = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", self.product.id),
            ("location_id", "=", self.location.id),
        ], limit=1)
        orderpoint.write({
            "product_min_qty": 100,
            "product_max_qty": 144,
            "qty_multiple": 12,
        })

        critical_templates = self.env["product.template"].search([
            ("refuge_stock_level", "=", "critical"),
        ])
        configured_templates = self.env["product.template"].search([
            ("refuge_stock_min_qty", ">", 0),
        ])

        self.assertIn(template, critical_templates)
        self.assertIn(template, configured_templates)

    def test_demo_loader_raises_critical_ingredient_thresholds(self):
        cointreau = self.env.ref("refuge_aventuriers.prod_cointreau_1l")
        quantity = self.env["stock.quant"]._get_available_quantity(cointreau, self.location)
        orderpoint = self.env["stock.warehouse.orderpoint"].search([
            ("product_id", "=", cointreau.id),
            ("location_id", "=", self.location.id),
        ], limit=1)

        self.assertTrue(orderpoint, "Les ingrédients critiques doivent avoir un seuil.")
        self.assertGreaterEqual(orderpoint.product_min_qty, math.ceil(quantity * 0.35))
        self.assertGreaterEqual(orderpoint.product_max_qty, orderpoint.product_min_qty * 3)

    def test_demo_loader_bootstraps_pos_accounting(self):
        company = self.env.company
        pos_config = self.env.ref("refuge_aventuriers.pos_config_refuge")

        self.assertEqual(company.chart_template, "fr")
        self.assertTrue(
            self.env["account.account"].search_count(
                self.env["account.account"]._check_company_domain(company)
            ),
            "Le POS doit disposer d'un plan comptable chargé.",
        )
        self.assertTrue(pos_config.journal_id, "Le POS doit avoir un journal principal.")
        self.assertTrue(pos_config.invoice_journal_id, "Le POS doit avoir un journal de facturation.")

        cash_methods = pos_config.payment_method_ids.filtered("is_cash_count")
        bank_methods = pos_config.payment_method_ids.filtered(lambda pm: pm.type == "bank")
        self.assertTrue(cash_methods, "Le POS doit proposer un moyen de paiement espèces.")
        self.assertTrue(bank_methods, "Le POS doit proposer un moyen de paiement carte.")
        self.assertIn("Espèces", cash_methods.mapped("name"))
        self.assertIn("Carte bancaire", bank_methods.mapped("name"))
        card_methods = bank_methods.filtered(lambda pm: pm.name == "Carte bancaire")
        self.assertFalse(any(card_methods.mapped("use_payment_terminal")))

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

    def test_pos_invoice_generation_skips_pdf_when_wkhtml_is_broken(self):
        order = self.env["pos.order"].search([], limit=1)
        self.assertTrue(order)
        contexts = []

        def _fake_parent(recordset):
            contexts.append(dict(recordset._context))
            return {"type": "ir.actions.act_window_close"}

        with patch.object(
            type(self.env["ir.actions.report"]),
            "get_wkhtmltopdf_state",
            return_value="broken",
        ), patch(
            "odoo.addons.point_of_sale.models.pos_order.PosOrder._generate_pos_order_invoice",
            autospec=True,
            side_effect=_fake_parent,
        ):
            order._generate_pos_order_invoice()

        self.assertEqual(len(contexts), 1)
        self.assertFalse(contexts[0]["generate_pdf"])

    def test_pos_invoice_generation_keeps_pdf_when_wkhtml_is_ok(self):
        order = self.env["pos.order"].search([], limit=1)
        self.assertTrue(order)
        contexts = []

        def _fake_parent(recordset):
            contexts.append(dict(recordset._context))
            return {"type": "ir.actions.act_window_close"}

        with patch.object(
            type(self.env["ir.actions.report"]),
            "get_wkhtmltopdf_state",
            return_value="ok",
        ), patch(
            "odoo.addons.point_of_sale.models.pos_order.PosOrder._generate_pos_order_invoice",
            autospec=True,
            side_effect=_fake_parent,
        ):
            order._generate_pos_order_invoice()

        self.assertEqual(len(contexts), 1)
        self.assertNotIn("generate_pdf", contexts[0])
