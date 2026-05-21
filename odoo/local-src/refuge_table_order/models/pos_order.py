import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    """Extension du POS Odoo — la même table pos.order reçoit les commandes saisies au
    comptoir (module POS natif) ET celles soumises depuis la table via QR Code (app OWL).
    Contrainte d'architecture du cahier des charges §3.4."""

    _inherit = "pos.order"

    _REFUGE_POS_UID_RE = re.compile(r"([0-9-]){14,}")

    @api.model
    def _refuge_reference_has_pos_uid(self, reference):
        return bool(reference and self._REFUGE_POS_UID_RE.search(reference))

    @api.model
    def _refuge_build_pos_reference(self, table_number=None, reference=None, moment=None):
        if self._refuge_reference_has_pos_uid(reference):
            return reference
        if isinstance(moment, str):
            moment = fields.Datetime.to_datetime(moment)
        moment = moment or fields.Datetime.now()
        number = table_number or "X"
        return f"QR/{number}/{moment:%Y%m%d%H%M%S%f}"

    @api.model_create_multi
    def create(self, vals_list):
        table_map = {}
        refuge_table_ids = {
            vals.get("refuge_table_id")
            for vals in vals_list
            if vals.get("refuge_table_id") and not vals.get("table_id")
        }
        if refuge_table_ids:
            for table in self.env["refuge.table"].browse(list(refuge_table_ids)).exists():
                if not table.restaurant_table_id:
                    table.sync_pos_restaurant_memory()
                if table.restaurant_table_id:
                    table_map[table.id] = {
                        "restaurant_table_id": table.restaurant_table_id.id,
                        "number": table.number,
                    }
        for vals in vals_list:
            table_info = table_map.get(vals.get("refuge_table_id")) if vals.get("refuge_table_id") else None
            if table_info and not vals.get("table_id"):
                vals["table_id"] = table_info["restaurant_table_id"]
            if vals.get("refuge_source") == "qr":
                vals["pos_reference"] = self._refuge_build_pos_reference(
                    table_number=table_info and table_info["number"],
                    reference=vals.get("pos_reference"),
                    moment=vals.get("date_order"),
                )
        return super().create(vals_list)

    @api.model
    def normalize_refuge_pos_references(self):
        orders = self.search([("refuge_source", "=", "qr")])
        for order in orders:
            updates = {}
            if order.refuge_table_id and not order.table_id:
                if not order.refuge_table_id.restaurant_table_id:
                    order.refuge_table_id.sync_pos_restaurant_memory()
                if order.refuge_table_id.restaurant_table_id:
                    updates["table_id"] = order.refuge_table_id.restaurant_table_id.id
            if not self._refuge_reference_has_pos_uid(order.pos_reference):
                updates["pos_reference"] = self._refuge_build_pos_reference(
                    table_number=order.refuge_table_id.number if order.refuge_table_id else None,
                    reference=order.pos_reference,
                    moment=order.date_order or order.create_date,
                )
            if updates:
                order.write(updates)
        return True

    @api.model
    def cleanup_refuge_table_drafts(self):
        active_config = self.env["refuge.table"]._refuge_pos_config()
        self.normalize_refuge_pos_references()
        qr_drafts = self.search([
            ("refuge_source", "=", "qr"),
            ("state", "=", "draft"),
        ])
        if qr_drafts.filtered("to_invoice"):
            qr_drafts.filtered("to_invoice").write({"to_invoice": False})
        legacy_drafts = qr_drafts.filtered(lambda order: active_config and order.config_id != active_config)
        if legacy_drafts:
            legacy_drafts.write({"state": "cancel"})
        return True

    @api.model
    def export_for_ui_table_draft(self, table_ids):
        table_ids = list(table_ids or [])
        if not table_ids:
            return []
        tables = self.env["restaurant.table"].browse(table_ids).exists()
        if not tables:
            return []
        config_ids = tables.mapped("floor_id.pos_config_ids")
        trusted_config_ids = config_ids.mapped("trusted_config_ids")
        allowed_config_ids = (config_ids | trusted_config_ids).ids
        domain = [
            ("state", "=", "draft"),
            ("table_id", "in", tables.ids),
        ]
        if allowed_config_ids:
            domain.append(("config_id", "in", allowed_config_ids))
        orders = self.search(domain)
        return orders.export_for_ui()

    refuge_table_id = fields.Many2one(
        "refuge.table",
        string="Table (QR)",
        help="Renseignée si la commande provient de l'application de commande sur table.",
        ondelete="set null",
        index=True,
    )
    refuge_source = fields.Selection(
        [("pos", "Comptoir (POS)"), ("qr", "Table (QR Code)")],
        string="Origine",
        default="pos",
        index=True,
    )
    refuge_kitchen_status = fields.Selection(
        [
            ("new", "Nouvelle"),
            ("in_preparation", "En préparation"),
            ("ready", "Prête"),
            ("served", "Servie"),
        ],
        string="Statut barman",
        default="new",
        index=True,
        help="Cycle de vie côté espace barman. 'Prête' signale au service que la "
             "commande peut être portée à la table ; le paiement reste au comptoir.",
    )
    refuge_barman_user_id = fields.Many2one(
        "res.users",
        string="Barman en charge",
        copy=False,
        index=True,
        help="Barman qui a pris la commande en charge (via « Démarrer la "
             "préparation » ou « Reprendre »). Vide tant qu'elle est dans "
             "la colonne Nouvelles.",
    )
    refuge_status_since = fields.Datetime(
        string="Depuis (étape barman)",
        copy=False,
        default=fields.Datetime.now,
        help="Horodatage du dernier changement de statut barman. Sert au "
             "compte à rebours de 5 min par étape dans l'Espace barman.",
    )
    refuge_loyalty_points_pending = fields.Integer(
        string="Points fidélité à créditer",
        copy=False,
        help="Points gagnés (1 pt/€) en attente : crédités uniquement quand "
             "la commande passe à 'Servie'.",
    )
    refuge_loyalty_credited = fields.Boolean(
        string="Points fidélité crédités",
        copy=False,
        help="Anti-double-crédit : passe à True une fois les points gagnés "
             "versés sur la carte du client.",
    )
    refuge_stock_picking_id = fields.Many2one(
        "stock.picking",
        string="Livraison stock",
        copy=False,
        readonly=True,
        help="Bon de sortie lié à la commande. Pour le QR, il est créé au passage "
             "à 'Servie'. Pour le POS comptoir, il reprend le picking Odoo natif, "
             "avec explosion des cocktails en ingrédients.",
    )

    # -------------------------------------------------------------- stock

    def write(self, vals):
        # Tout changement d'étape barman réarme le timer de 5 min.
        if "refuge_kitchen_status" in vals and "refuge_status_since" not in vals:
            vals = dict(vals)
            vals["refuge_status_since"] = fields.Datetime.now()
        res = super().write(vals)
        if vals.get("refuge_kitchen_status") == "served":
            for order in self:
                if order.refuge_source == "qr" and not order.refuge_stock_picking_id:
                    order._refuge_deliver_to_table()
                order._refuge_credit_loyalty()
        return res

    def _create_order_picking(self):
        self.ensure_one()
        # Les commandes QR ont déjà une sortie stock dédiée au moment du
        # service : ne pas déclencher un second picking à l'encaissement.
        if self.refuge_source == "qr":
            return
        super()._create_order_picking()
        outgoing = self.picking_ids.filtered(
            lambda picking: picking.picking_type_id.code == "outgoing" and picking.state != "cancel"
        )[:1]
        if outgoing and self.refuge_stock_picking_id != outgoing:
            self.refuge_stock_picking_id = outgoing.id

    def _refuge_credit_loyalty(self):
        """Crédite les points gagnés sur la carte fidélité — une seule fois,
        au passage à 'Servie' (cf. découplage gain/dépense)."""
        self.ensure_one()
        if self.refuge_loyalty_credited or not self.partner_id:
            return
        pending = int(self.refuge_loyalty_points_pending or 0)
        if pending > 0:
            card = self.partner_id.refuge_loyalty_card(create_if_missing=True)
            card.sudo().write({"points": (card.points or 0) + pending})
        # Marqué crédité même si 0 pt (évite tout retraitement ultérieur).
        self.refuge_loyalty_credited = True

    def _refuge_get_delivery_picking_type(self):
        """Retourne le type d'opération pour la livraison (sortie) depuis l'entrepôt."""
        warehouse = self.env["stock.warehouse"].search([], limit=1)
        if not warehouse:
            raise UserError(_("Aucun entrepôt configuré, impossible de livrer la commande."))
        return warehouse.out_type_id

    def _refuge_explode_lines(self):
        """Pour chaque ligne, renvoie [(product, qty)].

        Si la ligne a une BoM de type `phantom` (kit cocktail), on renvoie les
        composants avec les quantités résultantes. Sinon, on renvoie la ligne telle
        quelle. Les produits non stockables (`type != 'product'`) sont ignorés : ils
        n'ont pas d'impact stock.
        """
        self.ensure_one()
        Bom = self.env["mrp.bom"].sudo()
        out = []
        for line in self.lines:
            product = line.product_id
            qty = line.qty
            bom = Bom._bom_find(product, company_id=self.company_id.id,
                                bom_type="phantom").get(product)
            if bom:
                _boms, components = bom.sudo().explode(product, qty)
                for comp_line, comp_data in components:
                    comp_product = comp_line.product_id
                    comp_qty = comp_data["qty"]
                    if comp_product.type == "product":
                        out.append((comp_product, comp_qty))
            elif product.type == "product":
                out.append((product, qty))
        return out

    def _refuge_deliver_to_table(self):
        """Crée un bon de sortie (stock.picking + stock.moves) représentant la
        livraison physique de la commande QR. Les stocks d'ingrédients sont
        décrémentés automatiquement via la validation du picking.
        """
        self.ensure_one()
        components = self._refuge_explode_lines()
        if not components:
            return False

        picking_type = self._refuge_get_delivery_picking_type()
        src_location = picking_type.default_location_src_id or \
            self.env.ref("stock.stock_location_stock")
        dest_location = picking_type.default_location_dest_id or \
            self.env.ref("stock.stock_location_customers")

        picking = self.env["stock.picking"].sudo().create({
            "picking_type_id": picking_type.id,
            "location_id": src_location.id,
            "location_dest_id": dest_location.id,
            "origin": f"QR {self.pos_reference or self.name}",
            "partner_id": self.partner_id.id or False,
            "company_id": self.company_id.id,
        })

        # Agrège les composants identiques (si plusieurs lignes utilisent le même ingrédient)
        merged = {}
        for product, qty in components:
            merged[product.id] = merged.get(product.id, 0.0) + qty

        for product_id, qty in merged.items():
            product = self.env["product.product"].browse(product_id)
            self.env["stock.move"].sudo().create({
                "name": product.display_name,
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "picking_id": picking.id,
                "location_id": src_location.id,
                "location_dest_id": dest_location.id,
                "company_id": self.company_id.id,
            })

        picking.action_confirm()
        picking.action_assign()
        # Quantités réellement livrées = demandées (pas de réserve partielle).
        # En Odoo 17, le champ sur stock.move s'appelle `quantity` (avant 16.0
        # c'était `quantity_done`).
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        try:
            picking._action_done()
        except Exception as e:  # noqa: BLE001
            _logger.warning("[refuge_table_order] Stock move failed for order %s: %s",
                            self.id, e)
            # On garde le picking en assigned si validation échoue (stock insuffisant
            # par ex.) — le barman est notifié en front-end via le flag returned dans
            # les orders.
        self.refuge_stock_picking_id = picking.id
        return picking
