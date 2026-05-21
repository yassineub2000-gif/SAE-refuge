from odoo.tests.common import TransactionCase


class TestRefugePosCounterFlow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.config = cls.env.ref("refuge_aventuriers.pos_config_refuge")
        cls.program = cls.env.ref("refuge_aventuriers.loyalty_refuge_program")
        cls.cocktail = cls.env.ref("refuge_aventuriers.prod_margarita")
        cls.beer = cls.env.ref("refuge_aventuriers.prod_vitus_50_cl")
        cls.tequila = cls.env.ref("refuge_aventuriers.prod_tequila_75cl")
        cls.cointreau = cls.env.ref("refuge_aventuriers.prod_cointreau_1l")
        cls.lime = cls.env.ref("refuge_aventuriers.prod_citron_vert_la_piece")
        cls.partner = cls.env.ref("refuge_aventuriers.partner_cli_jean_martin")

    def _open_session(self):
        return self.config.current_session_id or self.env["pos.session"].create({
            "config_id": self.config.id,
        })

    def test_pos_config_is_ready_for_counter_sales(self):
        self.assertIn(self.config, self.program.pos_config_ids)
        self.assertEqual(
            self.config.iface_start_categ_id,
            self.env.ref("refuge_aventuriers.pos_cat_cocktail"),
        )
        self.assertEqual(
            set(self.config.iface_available_categ_ids.ids),
            {
                self.env.ref("refuge_aventuriers.pos_cat_cocktail").id,
                self.env.ref("refuge_aventuriers.pos_cat_biere").id,
                self.env.ref("refuge_aventuriers.pos_cat_vin_rouge").id,
                self.env.ref("refuge_aventuriers.pos_cat_vin_blanc").id,
                self.env.ref("refuge_aventuriers.pos_cat_alcool_fort").id,
                self.env.ref("refuge_aventuriers.pos_cat_soft").id,
            },
        )
        self.assertTrue(
            {"Espèces", "Carte bancaire"}.issubset(
                set(self.config.payment_method_ids.mapped("name"))
            )
        )
        card_methods = self.config.payment_method_ids.filtered(lambda pm: pm.name == "Carte bancaire")
        self.assertTrue(card_methods)
        self.assertTrue(all(method.type == "bank" for method in card_methods))
        self.assertFalse(any(card_methods.mapped("use_payment_terminal")))
        self.assertEqual(
            self.config.company_id.point_of_sale_update_stock_quantities,
            "real",
        )

    def test_counter_sale_explodes_cocktail_bom_in_stock_moves(self):
        session = self._open_session()
        order = self.env["pos.order"].create({
            "session_id": session.id,
            "amount_tax": 0.0,
            "amount_total": self.cocktail.lst_price + self.beer.lst_price,
            "amount_paid": self.cocktail.lst_price + self.beer.lst_price,
            "amount_return": 0.0,
            "pos_reference": "TEST/POS/COUNTER/0001",
            "lines": [
                (0, 0, {
                    "name": "L1",
                    "product_id": self.cocktail.id,
                    "qty": 1,
                    "price_unit": self.cocktail.lst_price,
                    "price_subtotal": self.cocktail.lst_price,
                    "price_subtotal_incl": self.cocktail.lst_price,
                }),
                (0, 0, {
                    "name": "L2",
                    "product_id": self.beer.id,
                    "qty": 1,
                    "price_unit": self.beer.lst_price,
                    "price_subtotal": self.beer.lst_price,
                    "price_subtotal_incl": self.beer.lst_price,
                }),
            ],
        })

        order._create_order_picking()

        self.assertTrue(order.refuge_stock_picking_id)
        moved_products = order.refuge_stock_picking_id.move_ids.product_id
        self.assertNotIn(self.cocktail, moved_products)
        self.assertIn(self.beer, moved_products)
        self.assertIn(self.tequila, moved_products)
        self.assertIn(self.cointreau, moved_products)
        self.assertIn(self.lime, moved_products)

    def test_qr_order_keeps_custom_stock_timing(self):
        session = self._open_session()
        order = self.env["pos.order"].create({
            "session_id": session.id,
            "refuge_source": "qr",
            "amount_tax": 0.0,
            "amount_total": self.cocktail.lst_price,
            "amount_paid": self.cocktail.lst_price,
            "amount_return": 0.0,
            "pos_reference": "TEST/QR/0001",
            "lines": [
                (0, 0, {
                    "name": "L1",
                    "product_id": self.cocktail.id,
                    "qty": 1,
                    "price_unit": self.cocktail.lst_price,
                    "price_subtotal": self.cocktail.lst_price,
                    "price_subtotal_incl": self.cocktail.lst_price,
                }),
            ],
        })

        order._create_order_picking()

        self.assertFalse(order.picking_ids)
        self.assertFalse(order.refuge_stock_picking_id)

    def test_qr_order_served_creates_single_stock_picking_and_loyalty_once(self):
        session = self._open_session()
        card = self.partner.refuge_loyalty_card(create_if_missing=True)
        initial_points = card.points
        order = self.env["pos.order"].create({
            "session_id": session.id,
            "refuge_source": "qr",
            "partner_id": self.partner.id,
            "refuge_loyalty_points_pending": 8,
            "amount_tax": 0.0,
            "amount_total": self.cocktail.lst_price,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "pos_reference": "TEST/QR/SERVED/0001",
            "lines": [
                (0, 0, {
                    "name": "L1",
                    "product_id": self.cocktail.id,
                    "qty": 1,
                    "price_unit": self.cocktail.lst_price,
                    "price_subtotal": self.cocktail.lst_price,
                    "price_subtotal_incl": self.cocktail.lst_price,
                }),
            ],
        })

        order.write({"refuge_kitchen_status": "served"})
        first_picking = order.refuge_stock_picking_id
        order.write({"refuge_kitchen_status": "served"})
        card.invalidate_recordset(["points"])
        order.invalidate_recordset(["refuge_stock_picking_id", "refuge_loyalty_credited"])

        self.assertTrue(first_picking)
        self.assertEqual(order.refuge_stock_picking_id, first_picking)
        self.assertEqual(card.points, initial_points + 8)
        self.assertTrue(order.refuge_loyalty_credited)
