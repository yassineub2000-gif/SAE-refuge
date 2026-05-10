"""Routes publiques et JSON-RPC de l'application commande sur table.

Architecture (cahier des charges §3.5, livrable 3) :
- Une page HTML publique par table : /refuge/table/<token> → bundle OWL client.
- Une page HTML authentifiée barman : /refuge/barman → bundle OWL barman.
- Routes JSON (type='json', auth='public' pour le client, 'user' pour le barman) :
  * /refuge/api/table/<token>/menu      → catalogue (produits POS par catégorie)
  * /refuge/api/table/<token>/submit    → création d'un pos.order (refuge_source='qr')
  * /refuge/api/barman/orders           → liste des commandes en attente (polling ≤ 10 s)
  * /refuge/api/barman/set_status       → transition in_preparation → ready → served
"""

import logging
from datetime import datetime, timedelta

from odoo import fields, http
from odoo.exceptions import UserError
from odoo.http import request

_logger = logging.getLogger(__name__)

_POLLING_WINDOW_HOURS = 12

# Paliers fidélité (cahier des charges §3.1). Tuple (points, type, valeur).
_LOYALTY_TIERS = [
    {"points": 50,  "kind": "percent", "value": 5,   "label": "−5 % sur la commande"},
    {"points": 100, "kind": "percent", "value": 10,  "label": "−10 % sur la commande"},
    {"points": 200, "kind": "amount",  "value": 8.0, "label": "Boisson offerte (8 € max)"},
]


def _pin_is_valid(pin):
    pin = (pin or "").strip()
    return pin.isdigit() and 4 <= len(pin) <= 6


def _serialize_partner(partner):
    return {
        "id": partner.id,
        "name": partner.display_name,
        "email": partner.email or "",
        "points": partner.refuge_loyalty_points(),
        "tiers": [
            {**t, "available": partner.refuge_loyalty_points() >= t["points"]}
            for t in _LOYALTY_TIERS
        ],
    }


class RefugeTableOrderController(http.Controller):

    # ---------------------------------------------------------------- pages HTML

    @http.route("/refuge/menu", type="http", auth="user")
    def page_menu_preview(self, **kw):
        """Aperçu admin de l'app menu client : redirige vers la première table active."""
        table = request.env["refuge.table"].sudo().search([("active", "=", True)], limit=1, order="number")
        if not table:
            raise UserError("Aucune table active n'est configurée.")
        return request.redirect(f"/refuge/table/{table.token}")

    @http.route("/refuge/table/<string:token>", type="http", auth="public", website=False)
    def page_client(self, token, **kw):
        table = request.env["refuge.table"].sudo().search([("token", "=", token)], limit=1)
        if not table:
            return request.not_found()
        return request.render(
            "refuge_table_order.client_page",
            {"table_number": table.number, "table_label": table.name or "", "table_token": token},
        )

    @http.route("/refuge/barman", type="http", auth="user")
    def page_barman(self, **kw):
        return request.render("refuge_table_order.barman_page", {})

    # ------------------------------------------------------------- API (JSON-RPC)

    @http.route("/refuge/api/table/<string:token>/menu", type="json", auth="public")
    def api_menu(self, token, **kw):
        table = request.env["refuge.table"].sudo().search([("token", "=", token)], limit=1)
        if not table:
            return {"error": "invalid_token"}
        # On reprend strictement les produits disponibles au POS pour cohabiter
        # avec la config du Point de Vente natif.
        products = request.env["product.product"].sudo().search(
            [("available_in_pos", "=", True), ("sale_ok", "=", True)],
            order="pos_categ_ids, name",
        )
        by_cat = {}
        for p in products:
            cat_name = p.pos_categ_ids[:1].name or "Autres"
            # On utilise l'URL `/web/image` (publique via `auth='public'` côté
            # controller web de base) plutôt que d'embarquer le base64 dans le
            # payload JSON (plus lourd, pas cacheable).
            # `?unique=<timestamp>` sert de cache-buster : dès qu'on écrit une
            # nouvelle image sur le produit, `write_date` change et l'URL aussi,
            # ce qui force le navigateur à retélécharger au lieu de servir
            # l'ancienne version cachée.
            if p.image_256:
                stamp = int(p.write_date.timestamp()) if p.write_date else 0
                image_url = f"/web/image/product.product/{p.id}/image_256?unique={stamp}"
            else:
                image_url = ""
            by_cat.setdefault(cat_name, []).append(
                {
                    "id": p.id,
                    "name": p.display_name,
                    "price": p.lst_price,
                    "description": p.description_sale or "",
                    "image_url": image_url,
                }
            )
        return {
            "table": {"number": table.number, "label": table.name or ""},
            "categories": [{"name": k, "products": v} for k, v in by_cat.items()],
        }

    # ----------------------------------------------------- Authentification client

    @http.route("/refuge/api/table/<string:token>/auth/login", type="json", auth="public")
    def api_login(self, token, email=None, pin=None, **kw):
        if not request.env["refuge.table"].sudo().search_count([("token", "=", token)]):
            return {"error": "invalid_token"}
        if not (email and _pin_is_valid(pin)):
            return {"error": "missing_credentials"}
        partner = request.env["res.partner"].sudo().search(
            [("email", "=ilike", email.strip()), ("refuge_client_pin", "=", pin.strip())], limit=1,
        )
        if not partner:
            return {"error": "invalid_credentials"}
        partner.refuge_loyalty_card(create_if_missing=True)
        return {"ok": True, "partner": _serialize_partner(partner)}

    @http.route("/refuge/api/table/<string:token>/auth/signup", type="json", auth="public")
    def api_signup(self, token, name=None, email=None, pin=None, **kw):
        if not request.env["refuge.table"].sudo().search_count([("token", "=", token)]):
            return {"error": "invalid_token"}
        name = (name or "").strip()
        email = (email or "").strip()
        if not name or not email or not _pin_is_valid(pin):
            return {"error": "missing_fields"}
        Partner = request.env["res.partner"].sudo()
        if Partner.search_count([("email", "=ilike", email)]):
            return {"error": "email_exists"}
        partner = Partner.create({
            "name": name, "email": email,
            "refuge_client_pin": pin.strip(),
            "customer_rank": 1,
        })
        partner.refuge_loyalty_card(create_if_missing=True)
        return {"ok": True, "partner": _serialize_partner(partner)}

    @http.route("/refuge/api/table/<string:token>/submit", type="json", auth="public")
    def api_submit(self, token, lines=None, partner_id=None, pin=None, use_tier=None, **kw):
        """Crée une pos.order avec refuge_source='qr'. lines: [{product_id, qty}, ...]

        Optionnel : ``partner_id`` + ``pin`` (re-vérification) attache le client
        et ``use_tier`` (50/100/200) applique la réduction fidélité associée et
        débite la carte du nombre de points correspondant.
        """
        table = request.env["refuge.table"].sudo().search([("token", "=", token)], limit=1)
        if not table:
            return {"error": "invalid_token"}
        if not lines:
            return {"error": "empty_cart"}
        PosConfig = request.env["pos.config"].sudo()
        config = PosConfig.search([], limit=1, order="id")
        if not config:
            return {"error": "no_pos_config"}
        # Ouvrir une session si aucune n'est active
        session = request.env["pos.session"].sudo().search(
            [("config_id", "=", config.id), ("state", "=", "opened")], limit=1
        )
        if not session:
            session = request.env["pos.session"].sudo().create({"config_id": config.id})
            session.action_pos_session_open()

        # Validation client + tier fidélité ----------------------------------
        partner = request.env["res.partner"]
        loyalty_card = request.env["loyalty.card"]
        tier = None
        if partner_id:
            partner = request.env["res.partner"].sudo().browse(int(partner_id)).exists()
            if not partner or partner.refuge_client_pin != (pin or "").strip():
                return {"error": "invalid_credentials"}
            loyalty_card = partner.refuge_loyalty_card(create_if_missing=True)
            if use_tier:
                tier = next((t for t in _LOYALTY_TIERS if t["points"] == int(use_tier)), None)
                if not tier:
                    return {"error": "invalid_tier"}
                if (loyalty_card.points or 0) < tier["points"]:
                    return {"error": "insufficient_points"}

        # Construction des lignes -------------------------------------------
        products = request.env["product.product"].sudo().browse([int(l["product_id"]) for l in lines])
        prod_by_id = {p.id: p for p in products}
        order_lines, subtotal = [], 0.0
        for line in lines:
            pid = int(line["product_id"])
            qty = float(line.get("qty") or 1)
            prod = prod_by_id.get(pid)
            if not prod or not prod.available_in_pos:
                return {"error": "invalid_product", "product_id": pid}
            price = prod.lst_price
            subtotal += price * qty
            order_lines.append(
                (0, 0, {"product_id": pid, "qty": qty, "price_unit": price,
                        "price_subtotal": price * qty, "price_subtotal_incl": price * qty})
            )

        # Réduction fidélité comme ligne négative ----------------------------
        discount_amount = 0.0
        if tier:
            if tier["kind"] == "percent":
                discount_amount = round(subtotal * tier["value"] / 100.0, 2)
            else:
                discount_amount = min(tier["value"], subtotal)
            discount_product = request.env.ref(
                "refuge_table_order.product_loyalty_discount", raise_if_not_found=False,
            )
            if discount_product and discount_amount > 0:
                order_lines.append(
                    (0, 0, {
                        "product_id": discount_product.id, "qty": 1,
                        "price_unit": -discount_amount,
                        "price_subtotal": -discount_amount,
                        "price_subtotal_incl": -discount_amount,
                        "discount": 0,
                    })
                )

        total = subtotal - discount_amount
        order = request.env["pos.order"].sudo().create({
            "session_id": session.id,
            "refuge_table_id": table.id,
            "refuge_source": "qr",
            "refuge_kitchen_status": "new",
            "partner_id": partner.id or False,
            "lines": order_lines,
            "amount_tax": 0.0,
            "amount_total": total,
            "amount_paid": 0.0,
            "amount_return": 0.0,
            "pos_reference": f"QR/{table.number}/{datetime.utcnow():%H%M%S}",
        })

        # Débit / crédit de la carte fidélité --------------------------------
        if partner:
            earned = int(total)  # 1 pt / € — cahier des charges §3.1
            spent = tier["points"] if tier else 0
            new_points = max(0, (loyalty_card.points or 0) - spent + earned)
            loyalty_card.sudo().write({"points": new_points})
            partner.sudo().write({"refuge_last_order_date": fields.Date.context_today(partner)})

        _logger.info("[refuge_table_order] QR order %s created for table %s (partner=%s, tier=%s)",
                     order.id, table.number, partner.id or "-", tier and tier["points"])
        return {
            "ok": True, "order_id": order.id, "reference": order.pos_reference,
            "discount": discount_amount,
            "points_balance": partner.refuge_loyalty_points() if partner else None,
        }

    @http.route("/refuge/api/barman/orders", type="json", auth="user")
    def api_barman_orders(self, **kw):
        """Retourne les commandes QR actives (non servies) depuis les 12 dernières heures."""
        since = datetime.utcnow() - timedelta(hours=_POLLING_WINDOW_HOURS)
        orders = request.env["pos.order"].search([
            ("refuge_source", "=", "qr"),
            ("refuge_kitchen_status", "in", ["new", "in_preparation", "ready"]),
            ("create_date", ">=", since),
        ], order="create_date asc")
        return {
            "orders": [
                {
                    "id": o.id,
                    "reference": o.pos_reference,
                    "table": o.refuge_table_id.number or "?",
                    "table_label": o.refuge_table_id.name or "",
                    "status": o.refuge_kitchen_status,
                    "created": o.create_date.isoformat() if o.create_date else None,
                    "total": o.amount_total,
                    "lines": [
                        {"name": l.product_id.display_name, "qty": l.qty}
                        for l in o.lines
                    ],
                    "partner_id": o.partner_id.id or False,
                    "partner_name": o.partner_id.display_name if o.partner_id else "",
                    "stock_picking_state": o.refuge_stock_picking_id.state or False,
                }
                for o in orders
            ],
            "fetched_at": datetime.utcnow().isoformat(),
        }

    @http.route("/refuge/api/barman/set_status", type="json", auth="user")
    def api_barman_set_status(self, order_id=None, status=None, **kw):
        if status not in ("new", "in_preparation", "ready", "served"):
            return {"error": "invalid_status"}
        order = request.env["pos.order"].browse(int(order_id)).exists()
        if not order:
            return {"error": "not_found"}
        order.write({"refuge_kitchen_status": status})
        # Retourne l'état mis à jour pour que l'UI sache si le picking stock a
        # été créé (utile pour le rapport du barman, surtout en cas d'échec).
        return {
            "ok": True,
            "stock_picking_id": order.refuge_stock_picking_id.id or False,
            "stock_picking_state": order.refuge_stock_picking_id.state or False,
        }

    # -------------------------------------------------------- clients (barman)

    @http.route("/refuge/api/barman/partners/search", type="json", auth="user")
    def api_barman_search_partners(self, query="", limit=10, **kw):
        """Autocomplete client — le barman peut chercher par nom, email ou téléphone."""
        query = (query or "").strip()
        domain = [("customer_rank", ">", 0)]
        if query:
            domain = ["&", domain[0],
                      "|", "|",
                      ("name", "ilike", query),
                      ("email", "ilike", query),
                      ("phone", "ilike", query)]
        partners = request.env["res.partner"].search(domain, limit=int(limit), order="name")
        return {
            "partners": [
                {
                    "id": p.id, "name": p.display_name,
                    "email": p.email or "", "phone": p.phone or "",
                    "loyalty_points": int(p.refuge_loyalty_points_initial or 0),
                    "loyalty_expired": bool(p.refuge_loyalty_expired),
                }
                for p in partners
            ],
        }

    @http.route("/refuge/api/barman/partners/create", type="json", auth="user")
    def api_barman_create_partner(self, name, email=None, phone=None, **kw):
        """Crée un nouveau client (res.partner) depuis l'espace barman.

        Vérifie l'unicité par email ou téléphone pour éviter les doublons causés
        par un barman qui recréerait un client déjà connu.
        """
        name = (name or "").strip()
        if not name:
            return {"error": "name_required"}
        email = (email or "").strip() or False
        phone = (phone or "").strip() or False

        # Anti-doublon : si email ou phone est fourni et correspond à un client
        # existant, on retourne ce client plutôt que d'en créer un deuxième.
        Partner = request.env["res.partner"]
        existing = Partner.browse()
        if email:
            existing = Partner.search([("email", "=ilike", email)], limit=1)
        if not existing and phone:
            existing = Partner.search([("phone", "=", phone)], limit=1)
        if existing:
            return {"ok": True, "id": existing.id, "name": existing.display_name,
                    "deduplicated": True}

        partner = Partner.create({
            "name": name, "email": email, "phone": phone,
            "customer_rank": 1, "is_company": False,
        })
        _logger.info("[refuge_table_order] Partner %s created by barman (uid=%s)",
                     partner.id, request.env.uid)
        return {"ok": True, "id": partner.id, "name": partner.display_name,
                "deduplicated": False}

    @http.route("/refuge/api/barman/orders/attach_partner", type="json", auth="user")
    def api_barman_attach_partner(self, order_id, partner_id, **kw):
        """Associe un client à une commande QR (utile pour créditer la fidélité)."""
        order = request.env["pos.order"].browse(int(order_id)).exists()
        if not order:
            return {"error": "order_not_found"}
        partner = request.env["res.partner"].browse(int(partner_id)).exists()
        if not partner:
            return {"error": "partner_not_found"}
        order.write({"partner_id": partner.id})
        return {"ok": True, "partner_name": partner.display_name}
