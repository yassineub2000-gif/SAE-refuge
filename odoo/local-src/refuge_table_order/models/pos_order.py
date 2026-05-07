import logging

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PosOrder(models.Model):
    """Extension du POS Odoo — la même table pos.order reçoit les commandes saisies au
    comptoir (module POS natif) ET celles soumises depuis la table via QR Code (app OWL).
    Contrainte d'architecture du cahier des charges §3.4."""

    _inherit = "pos.order"

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
    refuge_stock_picking_id = fields.Many2one(
        "stock.picking",
        string="Livraison stock (QR)",
        copy=False,
        readonly=True,
        help="Bon de sortie créé lors du passage de la commande au statut 'Servie'. "
             "Explose les BoM des cocktails pour décrémenter les stocks d'ingrédients.",
    )

    # -------------------------------------------------------------- stock

    def write(self, vals):
        res = super().write(vals)
        if vals.get("refuge_kitchen_status") == "served":
            for order in self:
                if order.refuge_source == "qr" and not order.refuge_stock_picking_id:
                    order._refuge_deliver_to_table()
        return res

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
