import base64
import io
import secrets
from urllib.parse import quote

from odoo import api, fields, models


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

    _sql_constraints = [
        ("token_unique", "unique(token)", "Le jeton QR doit être unique."),
        ("number_unique", "unique(number)", "Le numéro de table doit être unique."),
    ]

    def _qr_menu_label(self):
        self.ensure_one()
        return f"Table {self.number}" + (f" — {self.name}" if self.name else "")

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
        return records

    def write(self, vals):
        res = super().write(vals)
        if {"number", "name", "token", "active"} & vals.keys():
            self._sync_qr_menu()
        return res

    def unlink(self):
        menus = self.mapped("menu_id")
        actions = self.mapped("menu_action_id")
        res = super().unlink()
        menus.sudo().unlink()
        actions.sudo().unlink()
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
