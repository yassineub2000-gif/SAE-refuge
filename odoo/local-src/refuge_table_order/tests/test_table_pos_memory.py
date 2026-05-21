import re

from odoo.tests.common import TransactionCase


class TestRefugeTablePosMemory(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.pos_config = cls.env["refuge.table"]._refuge_pos_config()
        cls.refuge_table = cls.env.ref("refuge_table_order.table_1")
        cls.product = cls.env.ref("refuge_aventuriers.prod_vitus_50_cl")

    def _get_session(self):
        return self.pos_config.current_session_id or self.env["pos.session"].create({
            "config_id": self.pos_config.id,
        })

    def test_refuge_tables_are_synced_to_pos_restaurant(self):
        self.assertTrue(self.pos_config.module_pos_restaurant)
        self.assertTrue(self.refuge_table.restaurant_floor_id)
        self.assertTrue(self.refuge_table.restaurant_table_id)
        self.assertIn(self.pos_config, self.refuge_table.restaurant_floor_id.pos_config_ids)
        tables = self.env["refuge.table"].search([])
        self.assertEqual(len(tables), 10)
        self.assertEqual(
            len(tables.filtered("restaurant_table_id")),
            10,
            "Chaque table QR doit être synchronisée vers une table native du POS.",
        )

    def test_qr_order_gets_restaurant_table_memory(self):
        session = self._get_session()
        order = self.env["pos.order"].create({
            "session_id": session.id,
            "refuge_source": "qr",
            "refuge_table_id": self.refuge_table.id,
            "amount_tax": 0.0,
            "amount_total": self.product.lst_price,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "pos_reference": "QR/MEMORY/0001",
            "lines": [
                (0, 0, {
                    "name": "L1",
                    "product_id": self.product.id,
                    "qty": 1,
                    "price_unit": self.product.lst_price,
                    "price_subtotal": self.product.lst_price,
                    "price_subtotal_incl": self.product.lst_price,
                }),
            ],
        })

        self.assertEqual(order.table_id, self.refuge_table.restaurant_table_id)

    def test_sync_backfills_existing_qr_orders(self):
        session = self._get_session()
        order = self.env["pos.order"].with_context(tracking_disable=True).create({
            "session_id": session.id,
            "refuge_source": "qr",
            "refuge_table_id": self.refuge_table.id,
            "table_id": False,
            "amount_tax": 0.0,
            "amount_total": self.product.lst_price,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "pos_reference": "QR/MEMORY/0002",
            "lines": [
                (0, 0, {
                    "name": "L1",
                    "product_id": self.product.id,
                    "qty": 1,
                    "price_unit": self.product.lst_price,
                    "price_subtotal": self.product.lst_price,
                    "price_subtotal_incl": self.product.lst_price,
                }),
            ],
        })
        order.write({"table_id": False})

        self.env["refuge.table"].sync_pos_restaurant_memory()
        order.invalidate_recordset(["table_id"])

        self.assertEqual(order.table_id, self.refuge_table.restaurant_table_id)

    def test_table_draft_export_reloads_qr_articles(self):
        session = self._get_session()
        order = self.env["pos.order"].with_context(tracking_disable=True).create({
            "session_id": session.id,
            "refuge_source": "qr",
            "refuge_table_id": self.refuge_table.id,
            "table_id": False,
            "amount_tax": 0.0,
            "amount_total": self.product.lst_price,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "pos_reference": "QR/BROKEN/REF",
            "lines": [
                (0, 0, {
                    "name": "L1",
                    "product_id": self.product.id,
                    "qty": 1,
                    "price_unit": self.product.lst_price,
                    "price_subtotal": self.product.lst_price,
                    "price_subtotal_incl": self.product.lst_price,
                }),
            ],
        })
        order.write({"pos_reference": "QR/BROKEN/REF", "table_id": False})

        self.env["pos.order"].normalize_refuge_pos_references()
        payload = self.env["pos.order"].export_for_ui_table_draft(
            self.refuge_table.restaurant_table_id.ids
        )
        order.invalidate_recordset(["pos_reference", "table_id"])

        payload_by_id = {entry["id"]: entry for entry in payload}

        self.assertEqual(order.table_id, self.refuge_table.restaurant_table_id)
        self.assertRegex(order.pos_reference, re.compile(r"([0-9-]){14,}"))
        self.assertIn(order.id, payload_by_id)
        self.assertEqual(payload_by_id[order.id]["lines"][0][2]["product_id"], self.product.id)

    def test_table_draft_export_ignores_legacy_qr_orders_from_other_configs(self):
        other_config = self.env["pos.config"].search([
            ("id", "!=", self.pos_config.id),
        ], limit=1)
        other_session = other_config.current_session_id or self.env["pos.session"].create({
            "config_id": other_config.id,
        })
        legacy_order = self.env["pos.order"].create({
            "session_id": other_session.id,
            "refuge_source": "qr",
            "refuge_table_id": self.refuge_table.id,
            "table_id": self.refuge_table.restaurant_table_id.id,
            "amount_tax": 0.0,
            "amount_total": self.product.lst_price,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "pos_reference": "QR/LEGACY/0001",
            "lines": [
                (0, 0, {
                    "name": "L1",
                    "product_id": self.product.id,
                    "qty": 1,
                    "price_unit": self.product.lst_price,
                    "price_subtotal": self.product.lst_price,
                    "price_subtotal_incl": self.product.lst_price,
                }),
            ],
        })

        payload = self.env["pos.order"].export_for_ui_table_draft(
            self.refuge_table.restaurant_table_id.ids
        )

        self.assertNotIn(legacy_order.id, {entry["id"] for entry in payload})

    def test_table_draft_export_keeps_multiple_current_orders_for_same_table(self):
        session = self._get_session()
        orders = self.env["pos.order"]
        for reference in ("QR/MULTI/0001", "QR/MULTI/0002"):
            orders |= self.env["pos.order"].create({
                "session_id": session.id,
                "refuge_source": "qr",
                "refuge_table_id": self.refuge_table.id,
                "table_id": self.refuge_table.restaurant_table_id.id,
                "amount_tax": 0.0,
                "amount_total": self.product.lst_price,
                "amount_paid": 0.0,
                "amount_return": 0.0,
                "pos_reference": reference,
                "lines": [
                    (0, 0, {
                        "name": "L1",
                        "product_id": self.product.id,
                        "qty": 1,
                        "price_unit": self.product.lst_price,
                        "price_subtotal": self.product.lst_price,
                        "price_subtotal_incl": self.product.lst_price,
                    }),
                ],
            })

        payload = self.env["pos.order"].export_for_ui_table_draft(
            self.refuge_table.restaurant_table_id.ids
        )

        self.assertTrue(orders.ids)
        self.assertTrue(set(orders.ids).issubset({entry["id"] for entry in payload}))
