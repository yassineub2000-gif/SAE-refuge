import base64
import io
import secrets
from urllib.parse import quote

from odoo import api, fields, models


_REFUGE_DEFAULT_TABLES = {
    "refuge_table_order.table_1": {"number": "1", "name": "Salle 1", "token": "demo-token-table-1"},
    "refuge_table_order.table_2": {"number": "2", "name": "Salle 2", "token": "demo-token-table-2"},
    "refuge_table_order.table_3": {"number": "3", "name": "Salle 3", "token": "demo-token-table-3"},
    "refuge_table_order.table_4": {"number": "4", "name": "Salle 4", "token": "demo-token-table-4"},
    "refuge_table_order.table_5": {"number": "5", "name": "Salle 5", "token": "demo-token-table-5"},
    "refuge_table_order.table_6": {"number": "6", "name": "Salle 6", "token": "demo-token-table-6"},
    "refuge_table_order.table_7": {"number": "7", "name": "Salle 7", "token": "demo-token-table-7"},
    "refuge_table_order.table_8": {"number": "8", "name": "Salle 8", "token": "demo-token-table-8"},
    "refuge_table_order.table_9": {"number": "9", "name": "Salle 9", "token": "demo-token-table-9"},
    "refuge_table_order.table_10": {"number": "10", "name": "Salle 10", "token": "demo-token-table-10"},
}


class RefugeTable(models.Model):
    """Table physique du bar. Chaque table a un jeton unique utilisé dans l'URL du QR Code,
    indépendant de l'ID technique pour éviter qu'un client puisse incrémenter l'URL et
    basculer sur une autre table."""

    _name = "refuge.table"
    _description = "Table (QR Code commande client)"
    _order = "number"

    number = fields.Char(string="Numéro de table", required=True)
    name = fields.Char(string="Libellé", help="Ex. 'Terrasse 3', 'Comptoir'.")
    token = fields.Char(
        string="Jeton QR",
        required=True,
        copy=False,
        default=lambda self: secrets.token_urlsafe(16),
        help="Chaîne secrète intégrée dans l'URL du QR Code. Régénérer la valeur "
             "invalide tous les QR codes existants pour la table.",
    )
    active = fields.Boolean(default=True)
    qr_url = fields.Char(string="URL QR", compute="_compute_qr_url", store=False)
    qr_image = fields.Binary(
        string="QR Code",
        compute="_compute_qr_image",
        store=False,
        help="Image PNG du QR Code à imprimer et poser sur la table.",
    )
    qr_image_url = fields.Char(
        string="URL image QR",
        compute="_compute_qr_image",
        store=False,
        help="URL servant le rendu QR via le report barcode natif d'Odoo.",
    )

    menu_id = fields.Many2one(
        "ir.ui.menu",
        string="Entrée de menu QR",
        readonly=True,
        ondelete="set null",
        help="Sous-menu auto-généré sous Tables (QR) pour ouvrir l'app client.",
    )
    menu_action_id = fields.Many2one(
        "ir.actions.act_url",
        string="Action URL QR",
        readonly=True,
        ondelete="set null",
    )
    restaurant_floor_id = fields.Many2one(
        "restaurant.floor",
        string="Plan de salle POS",
        readonly=True,
        ondelete="set null",
        help="Plan de salle POS natif Odoo utilisé pour la mémoire de table.",
    )
    restaurant_table_id = fields.Many2one(
        "restaurant.table",
        string="Table POS",
        readonly=True,
        ondelete="set null",
        help="Table native du POS restaurant synchronisée avec cette table QR.",
    )

    _sql_constraints = [
        ("token_unique", "unique(token)", "Le jeton QR doit être unique."),
        ("number_unique", "unique(number)", "Le numéro de table doit être unique."),
    ]

    def _qr_menu_label(self):
        self.ensure_one()
        return f"Table {self.number}" + (f" — {self.name}" if self.name else "")

    def _restaurant_table_label(self):
        self.ensure_one()
        return f"Table {self.number}" + (f" - {self.name}" if self.name else "")

    def _refuge_sorted_by_number(self):
        return self.sorted(
            key=lambda table: (
                int(table.number) if str(table.number).isdigit() else 10**9,
                table.number or "",
            )
        )

    @api.model
    def _refuge_pos_config(self):
        refuge_config = self.env.ref("refuge_aventuriers.pos_config_refuge", raise_if_not_found=False)
        if refuge_config and refuge_config.module_pos_restaurant:
            return refuge_config
        restaurant_config = self.env["pos.config"].search([
            ("company_id", "=", (refuge_config.company_id.id if refuge_config else self.env.company.id)),
            ("module_pos_restaurant", "=", True),
            ("active", "=", True),
        ], limit=1, order="id")
        return restaurant_config or refuge_config

    @api.model
    def _ensure_refuge_restaurant_floor(self):
        pos_config = self._refuge_pos_config()
        if not pos_config:
            return self.env["restaurant.floor"]
        opened_sessions = pos_config.session_ids.filtered(lambda s: s.state != "closed")
        updates = {}
        if not pos_config.module_pos_restaurant and not opened_sessions:
            updates["module_pos_restaurant"] = True
        if not pos_config.iface_splitbill and not opened_sessions:
            updates["iface_splitbill"] = True
        if not pos_config.iface_printbill and not opened_sessions:
            updates["iface_printbill"] = True
        if not pos_config.iface_orderline_notes and not opened_sessions:
            updates["iface_orderline_notes"] = True
        if updates:
            pos_config.write(updates)

        floor = self.env["restaurant.floor"].search([
            ("name", "=", "Refuge des Aventuriers"),
            ("pos_config_ids", "=", pos_config.id),
        ], limit=1)
        if not floor:
            floor = pos_config.floor_ids[:1]
        if not floor:
            floor = self.env["restaurant.floor"].create({
                "name": "Refuge des Aventuriers",
                "background_color": "rgb(240, 232, 214)",
                "pos_config_ids": [(4, pos_config.id)],
            })
        else:
            vals = {}
            if floor.name != "Refuge des Aventuriers":
                vals["name"] = "Refuge des Aventuriers"
            if floor.background_color != "rgb(240, 232, 214)":
                vals["background_color"] = "rgb(240, 232, 214)"
            if pos_config not in floor.pos_config_ids:
                vals["pos_config_ids"] = [(4, pos_config.id)]
            if vals:
                floor.write(vals)
        if floor not in pos_config.floor_ids:
            pos_config.write({"floor_ids": [(4, floor.id)]})
        return floor

    @api.model
    def _refuge_apply_default_tables(self):
        for xmlid, values in _REFUGE_DEFAULT_TABLES.items():
            table = self.env.ref(xmlid, raise_if_not_found=False)
            if table:
                table.sudo().write(values)
        return True

    @api.model
    def _table_layout_values(self, index):
        # Plan compact et lisible pour 10 tables : 2 rangées de 5, avec un léger
        # décalage vertical sur la seconde rangée pour éviter l'effet "grille brute".
        columns = 5
        width = 118
        height = 88
        gap_h = 24
        gap_v = 42
        column = index % columns
        row = index // columns
        row_offset = 24 if row % 2 else 0
        return {
            "position_h": 52 + column * (width + gap_h),
            "position_v": 72 + row * (height + gap_v) + row_offset,
            "width": width,
            "height": height,
            "shape": "round",
            "color": "#8c5a35",
            "seats": 4,
        }

    def _sync_restaurant_table(self, floor):
        RestaurantTable = self.env["restaurant.table"].sudo()
        for index, rec in enumerate(self._refuge_sorted_by_number()):
            table = rec.restaurant_table_id
            if not table:
                table = RestaurantTable.search([
                    ("floor_id", "=", floor.id),
                    ("name", "in", [rec._restaurant_table_label(), rec.number]),
                ], limit=1)
            layout = self._table_layout_values(index)
            vals = {
                "name": rec._restaurant_table_label(),
                "floor_id": floor.id,
                "active": rec.active,
                **layout,
            }
            if table:
                table.write(vals)
            else:
                table = RestaurantTable.create(vals)
            rec.sudo().write({
                "restaurant_floor_id": floor.id,
                "restaurant_table_id": table.id,
            })

    def _sync_linked_pos_orders(self):
        for rec in self.filtered("restaurant_table_id"):
            self.env["pos.order"].sudo().search([
                ("refuge_table_id", "=", rec.id),
                ("table_id", "=", False),
            ]).write({"table_id": rec.restaurant_table_id.id})

    @api.model
    def sync_pos_restaurant_memory(self):
        tables = self.search([])
        if not tables:
            return True
        floor = self._ensure_refuge_restaurant_floor()
        if floor:
            tables._sync_restaurant_table(floor)
            tables._sync_linked_pos_orders()
        return True

    def _sync_qr_menu(self):
        parent = self.env.ref("refuge_table_order.menu_refuge_table", raise_if_not_found=False)
        if not parent:
            return
        ActUrl = self.env["ir.actions.act_url"].sudo()
        Menu = self.env["ir.ui.menu"].sudo()
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            label = rec._qr_menu_label()
            client_url = f"{base}/refuge/table/{rec.token}" if base else f"/refuge/table/{rec.token}"
            url = f"/report/barcode/QR/{quote(client_url, safe='')}?width=400&height=400"
            if rec.menu_action_id:
                rec.menu_action_id.write({"name": label, "url": url})
            else:
                rec.menu_action_id = ActUrl.create({"name": label, "url": url, "target": "new"})
            menu_vals = {
                "name": label,
                "parent_id": parent.id,
                "action": f"ir.actions.act_url,{rec.menu_action_id.id}",
                "active": rec.active,
            }
            if rec.menu_id:
                rec.menu_id.write(menu_vals)
            else:
                rec.menu_id = Menu.create(menu_vals)

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_qr_menu()
        self.sync_pos_restaurant_memory()
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"number", "name", "token", "active"} & vals.keys():
            self._sync_qr_menu()
            self.sync_pos_restaurant_memory()
        return res

    def unlink(self):
        menus = self.mapped("menu_id")
        actions = self.mapped("menu_action_id")
        restaurant_tables = self.mapped("restaurant_table_id")
        res = super().unlink()
        menus.sudo().unlink()
        actions.sudo().unlink()
        restaurant_tables.filtered(lambda table: not table.are_orders_still_in_draft()).sudo().unlink()
        return res

    @api.depends("token")
    def _compute_qr_url(self):
        base = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for rec in self:
            rec.qr_url = f"{base}/refuge/table/{rec.token}" if rec.token else ""

    @api.depends("qr_url")
    def _compute_qr_image(self):
        # On privilégie la librairie `qrcode` si elle est disponible (pas de
        # dépendance ajoutée ; elle est déjà présente dans l'image Odoo via
        # `python-qrcode`). Si absente, on retombe sur le report barcode natif
        # (`/report/barcode/QR?...`) affiché comme image distante.
        try:
            import qrcode  # noqa: F401
            have_qr = True
        except ImportError:
            have_qr = False

        for rec in self:
            if not rec.qr_url:
                rec.qr_image = False
                rec.qr_image_url = False
                continue
            rec.qr_image_url = (
                f"/report/barcode/QR?value={quote(rec.qr_url)}&width=400&height=400"
            )
            if have_qr:
                import qrcode as _qrcode

                img = _qrcode.make(rec.qr_url, box_size=10, border=2)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                rec.qr_image = base64.b64encode(buf.getvalue())
            else:
                rec.qr_image = False

    def action_rotate_token(self):
        for rec in self:
            rec.token = secrets.token_urlsafe(16)

    def action_print_qr(self):
        """Ouvre l'image QR dans un nouvel onglet pour impression directe."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.qr_image_url,
            "target": "new",
        }
