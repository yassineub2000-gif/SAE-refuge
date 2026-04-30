import base64
import json
from datetime import timedelta
from html import escape
from pathlib import Path

from odoo import api, fields, models


class RefugeDemoLoader(models.Model):
    _name = "refuge.demo.loader"
    _description = "Chargeur de donnees de demonstration du Refuge"

    _PRODUCT_IMAGE_THEMES = {
        "Bière": {
            "bg_start": "#24120c",
            "bg_end": "#8a4b1f",
            "accent": "#f5b642",
            "accent_soft": "#ffd98c",
            "label": "BIERE",
            "icon": "beer",
        },
        "Vin / Rouge": {
            "bg_start": "#1d0e16",
            "bg_end": "#7a1735",
            "accent": "#cf4263",
            "accent_soft": "#f2a0b4",
            "label": "VIN ROUGE",
            "icon": "wine_red",
        },
        "Vin / Blanc": {
            "bg_start": "#172110",
            "bg_end": "#6d7f29",
            "accent": "#d8d36b",
            "accent_soft": "#f1edaf",
            "label": "VIN BLANC",
            "icon": "wine_white",
        },
        "Cocktail": {
            "bg_start": "#0d2730",
            "bg_end": "#18818d",
            "accent": "#ff8d5d",
            "accent_soft": "#ffd2a7",
            "label": "COCKTAIL",
            "icon": "cocktail",
        },
        "Alcool Fort": {
            "bg_start": "#18151f",
            "bg_end": "#54416f",
            "accent": "#a97cff",
            "accent_soft": "#d8c0ff",
            "label": "SPIRITUEUX",
            "icon": "spirit",
        },
        "Soft": {
            "bg_start": "#0e2330",
            "bg_end": "#1b7197",
            "accent": "#5fd4ff",
            "accent_soft": "#c0f0ff",
            "label": "SOFT",
            "icon": "soft",
        },
        "Ingrédient": {
            "bg_start": "#172316",
            "bg_end": "#497449",
            "accent": "#8bd56b",
            "accent_soft": "#d8f0bf",
            "label": "INGREDIENT",
            "icon": "ingredient",
        },
    }

    @api.model
    def _load_raw_data(self):
        raw_path = Path(__file__).resolve().parent.parent / "data" / "_raw_data.json"
        return json.loads(raw_path.read_text(encoding="utf-8"))

    @api.model
    def _get_demo_location(self):
        return self.env.ref("stock.stock_location_stock")

    @api.model
    def _get_demo_warehouse(self):
        location = self._get_demo_location()
        return location.warehouse_id or self.env["stock.warehouse"].search([], limit=1)

    @api.model
    def _ensure_loyalty_program_on_pos(self):
        program = self.env.ref("refuge_aventuriers.loyalty_refuge_program")
        pos_config = self.env.ref("refuge_aventuriers.pos_config_refuge")
        if pos_config not in program.pos_config_ids:
            program.write({"pos_config_ids": [(4, pos_config.id)]})

    @api.model
    def _ensure_pos_payment_methods(self):
        """Attache Espèces + Carte au POS du bar et lie ses catégories produit.

        Sans cela, le POS refuse d'ouvrir une session (« aucun moyen de paiement »).
        On ne touche pas au POS si une session est déjà ouverte (Odoo bloque
        toute modification de `payment_method_ids` dans ce cas).
        """
        pos_config = self.env.ref("refuge_aventuriers.pos_config_refuge")
        Session = self.env["pos.session"].sudo()
        if Session.search_count([
            ("config_id", "=", pos_config.id),
            ("state", "!=", "closed"),
        ]):
            return  # une session est ouverte : on laisse le POS tranquille
        Method = self.env["pos.payment.method"].sudo()
        wanted = [("Espèces", "cash"), ("Carte bancaire", "bank")]
        methods = self.env["pos.payment.method"]
        for name, kind in wanted:
            existing = Method.search([("name", "=", name)], limit=1)
            if not existing:
                vals = {"name": name}
                if kind == "cash":
                    vals["is_cash_count"] = True
                existing = Method.create(vals)
            methods |= existing
        missing = methods - pos_config.payment_method_ids
        if missing:
            pos_config.write({"payment_method_ids": [(4, m.id) for m in missing]})
        pos_categs = self.env["pos.category"].sudo().search([])
        if pos_categs and not pos_config.iface_available_categ_ids:
            pos_config.write({"iface_available_categ_ids": [(6, 0, pos_categs.ids)]})

    @api.model
    def _seed_partner_activity(self):
        today = fields.Date.context_today(self)
        demo_offsets = {
            "partner_cli_jean_martin": 14,
            "partner_cli_sophie_durand": 40,
            "partner_cli_marc_leroy": 220,
            "partner_cli_celine_moreau": 28,
            "partner_cli_aurore_michel": 7,
            "partner_cli_isabelle_fontaine": 195,
        }
        for xmlid, days in demo_offsets.items():
            partner = self.env.ref(f"refuge_aventuriers.{xmlid}", raise_if_not_found=False)
            if partner and not partner.refuge_last_order_date:
                partner.refuge_last_order_date = today - timedelta(days=days)

    @api.model
    def _ensure_loyalty_cards(self, raw_data):
        program = self.env.ref("refuge_aventuriers.loyalty_refuge_program")
        for client in raw_data.get("clients", []):
            partner = self.env.ref(f"refuge_aventuriers.{client['id']}", raise_if_not_found=False)
            if not partner or not partner.refuge_loyalty_points_initial:
                continue
            existing = self.env["loyalty.card"].search([
                ("program_id", "=", program.id),
                ("partner_id", "=", partner.id),
            ], limit=1)
            if existing:
                continue
            self.env["loyalty.card"].create({
                "program_id": program.id,
                "partner_id": partner.id,
                "points": partner.refuge_loyalty_points_initial,
                "code": f"REFUGE-{partner.id:05d}",
            })

    @api.model
    def _product_image_lines(self, product_name, max_chars=14):
        words = product_name.replace("(", "").replace(")", "").replace("-", " - ").split()
        lines = []
        current = ""
        for word in words:
            candidate = (current + " " + word).strip()
            if len(candidate) <= max_chars or not current:
                current = candidate
                continue
            lines.append(current)
            current = word
        if current:
            lines.append(current)
        if len(lines) > 2:
            lines = [lines[0], " ".join(lines[1:])]
        return [line[:max_chars + 4].strip() for line in lines[:2]]

    @api.model
    def _product_image_icon(self, product_data, theme):
        icon = theme["icon"]
        name = product_data["name"].lower()
        accent = theme["accent"]
        accent_soft = theme["accent_soft"]
        if icon == "beer":
            return f"""
                <rect x="380" y="180" width="188" height="340" rx="48" fill="{accent}" opacity="0.28"/>
                <rect x="404" y="220" width="140" height="286" rx="32" fill="{accent}"/>
                <rect x="430" y="170" width="88" height="72" rx="28" fill="#fff5d7"/>
                <path d="M544 248h54c40 0 68 26 68 68s-28 68-68 68h-54" fill="none" stroke="{accent_soft}" stroke-width="24" stroke-linecap="round"/>
            """
        if icon == "wine_red":
            return f"""
                <rect x="430" y="156" width="88" height="320" rx="34" fill="{accent}"/>
                <rect x="455" y="118" width="38" height="72" rx="18" fill="{accent_soft}"/>
                <rect x="468" y="450" width="12" height="112" rx="6" fill="#f7e8eb"/>
                <rect x="402" y="562" width="144" height="16" rx="8" fill="#f7e8eb"/>
            """
        if icon == "wine_white":
            return f"""
                <rect x="430" y="156" width="88" height="320" rx="34" fill="{accent}"/>
                <rect x="455" y="118" width="38" height="72" rx="18" fill="#f6f1bf"/>
                <rect x="468" y="450" width="12" height="112" rx="6" fill="#faf7e0"/>
                <rect x="402" y="562" width="144" height="16" rx="8" fill="#faf7e0"/>
            """
        if icon == "cocktail":
            return f"""
                <path d="M318 190h312l-150 168v18h70v22h-70v114h-20V398h-70v-22h70v-18z" fill="{accent_soft}"/>
                <path d="M370 216h208l-102 114h-4z" fill="{accent}"/>
                <circle cx="584" cy="180" r="26" fill="{accent}"/>
                <path d="M564 198l-54 54" stroke="{accent_soft}" stroke-width="12" stroke-linecap="round"/>
            """
        if icon == "spirit":
            return f"""
                <rect x="398" y="152" width="152" height="342" rx="34" fill="{accent}"/>
                <rect x="438" y="116" width="72" height="72" rx="20" fill="{accent_soft}"/>
                <rect x="430" y="286" width="88" height="114" rx="18" fill="{accent_soft}" opacity="0.42"/>
                <circle cx="474" cy="530" r="74" fill="{accent_soft}" opacity="0.18"/>
            """
        if icon == "soft":
            return f"""
                <rect x="404" y="144" width="140" height="372" rx="44" fill="{accent}"/>
                <rect x="430" y="118" width="88" height="42" rx="18" fill="{accent_soft}"/>
                <rect x="434" y="262" width="80" height="132" rx="20" fill="#ffffff" opacity="0.24"/>
                <circle cx="580" cy="254" r="28" fill="{accent_soft}"/>
                <circle cx="624" cy="220" r="18" fill="{accent_soft}" opacity="0.55"/>
            """
        if "citron" in name:
            return f"""
                <circle cx="470" cy="332" r="112" fill="{accent}"/>
                <path d="M470 220v224M358 332h224M390 252l160 160M390 412l160-160" stroke="{accent_soft}" stroke-width="14" stroke-linecap="round"/>
                <ellipse cx="580" cy="206" rx="42" ry="20" fill="{accent_soft}" transform="rotate(-24 580 206)"/>
            """
        if "orange" in name:
            return f"""
                <circle cx="470" cy="332" r="112" fill="#ff9948"/>
                <path d="M470 220v224M358 332h224M390 252l160 160M390 412l160-160" stroke="#ffdcb4" stroke-width="14" stroke-linecap="round"/>
                <ellipse cx="580" cy="206" rx="42" ry="20" fill="{accent_soft}" transform="rotate(-24 580 206)"/>
            """
        if "menthe" in name:
            return f"""
                <path d="M474 196c94 0 152 70 152 156s-58 156-152 156-152-70-152-156 58-156 152-156z" fill="{accent}" opacity="0.14"/>
                <path d="M476 512c-12-142 30-268 156-292-6 124-110 262-156 292z" fill="{accent}"/>
                <path d="M468 512c12-142-30-268-156-292 6 124 110 262 156 292z" fill="{accent_soft}"/>
                <path d="M472 226v280" stroke="#eef7dd" stroke-width="10" stroke-linecap="round"/>
            """
        return f"""
            <rect x="408" y="156" width="132" height="350" rx="34" fill="{accent}"/>
            <rect x="442" y="122" width="64" height="60" rx="18" fill="{accent_soft}"/>
            <rect x="430" y="286" width="88" height="118" rx="18" fill="{accent_soft}" opacity="0.34"/>
        """

    @api.model
    def _product_image_svg(self, product_data):
        theme = self._PRODUCT_IMAGE_THEMES.get(
            product_data.get("category"),
            self._PRODUCT_IMAGE_THEMES["Ingrédient"],
        )
        title_lines = self._product_image_lines(product_data["name"])
        title_y = 694 if len(title_lines) == 1 else 666
        title_svg = []
        for index, line in enumerate(title_lines):
            title_svg.append(
                f'<text x="84" y="{title_y + (index * 52)}" '
                f'font-family="DejaVu Sans, Arial, sans-serif" font-size="44" '
                f'font-weight="700" fill="#f8f7f2">{escape(line)}</text>'
            )
        subtitle = escape(theme["label"])
        icon_svg = self._product_image_icon(product_data, theme)
        return f"""
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
                <defs>
                    <linearGradient id="bg" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stop-color="{theme['bg_start']}"/>
                        <stop offset="100%" stop-color="{theme['bg_end']}"/>
                    </linearGradient>
                    <linearGradient id="panel" x1="0%" y1="0%" x2="100%" y2="0%">
                        <stop offset="0%" stop-color="rgba(255,255,255,0.12)"/>
                        <stop offset="100%" stop-color="rgba(255,255,255,0.04)"/>
                    </linearGradient>
                </defs>
                <rect width="1024" height="1024" rx="72" fill="url(#bg)"/>
                <circle cx="826" cy="188" r="168" fill="{theme['accent']}" opacity="0.12"/>
                <circle cx="184" cy="850" r="132" fill="#ffffff" opacity="0.05"/>
                <rect x="64" y="64" width="896" height="896" rx="52" fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="4"/>
                <rect x="84" y="84" width="220" height="68" rx="34" fill="rgba(255,255,255,0.10)"/>
                <text x="194" y="128" text-anchor="middle"
                      font-family="DejaVu Sans, Arial, sans-serif" font-size="28"
                      font-weight="700" letter-spacing="3" fill="#f4efe5">{subtitle}</text>
                <g>{icon_svg}</g>
                <rect x="84" y="612" width="856" height="228" rx="38" fill="rgba(11,17,23,0.24)"/>
                {''.join(title_svg)}
                <text x="84" y="820" font-family="DejaVu Sans, Arial, sans-serif"
                      font-size="24" font-weight="600" fill="{theme['accent_soft']}" letter-spacing="4">
                    LE REFUGE DES AVENTURIERS
                </text>
            </svg>
        """.strip()

    @api.model
    def _get_product_image_path(self, product_id):
        products_dir = Path(__file__).resolve().parent.parent / "static" / "src" / "img" / "products"
        for suffix in (".jpg", ".jpeg", ".png", ".webp"):
            image_path = products_dir / f"{product_id}{suffix}"
            if image_path.exists():
                return image_path
        return None

    @api.model
    def _ensure_product_images(self, raw_data):
        for product_data in raw_data.get("products", []):
            product = self.env.ref(
                f"refuge_aventuriers.{product_data['id']}",
                raise_if_not_found=False,
            )
            if not product:
                continue
            image_path = self._get_product_image_path(product_data["id"])
            if image_path:
                product.image_1920 = base64.b64encode(image_path.read_bytes())
                continue
            if not product.image_1920:
                svg = self._product_image_svg(product_data)
                product.image_1920 = base64.b64encode(svg.encode("utf-8"))

    @api.model
    def _ensure_orderpoints(self, raw_data):
        location = self._get_demo_location()
        warehouse = self._get_demo_warehouse()
        buy_route = self.env.ref("purchase_stock.route_warehouse0_buy", raise_if_not_found=False)
        Orderpoint = self.env["stock.warehouse.orderpoint"]
        for product_data in raw_data.get("products", []):
            if (
                product_data.get("is_cocktail")
                or product_data.get("is_spirit_glass")
                or not product_data.get("stock_min")
            ):
                continue
            product = self.env.ref(
                f"refuge_aventuriers.{product_data['id']}",
                raise_if_not_found=False,
            )
            if not product or product.type != "product" or not product.purchase_ok:
                continue
            vals = {
                "product_id": product.id,
                "location_id": location.id,
                "warehouse_id": warehouse.id,
                "product_min_qty": float(product_data["stock_min"]),
                "product_max_qty": float(max(product_data["stock"], product_data["stock_min"] * 2)),
                "qty_multiple": float(max(product_data["stock_min"], 1)),
                "trigger": "auto",
            }
            if buy_route:
                vals["route_id"] = buy_route.id
            orderpoint = Orderpoint.search([
                ("product_id", "=", product.id),
                ("location_id", "=", location.id),
            ], limit=1)
            if orderpoint:
                orderpoint.write(vals)
            else:
                Orderpoint.create(vals)

    @api.model
    def _ensure_stock_quants(self, raw_data):
        location = self._get_demo_location()
        Quant = self.env["stock.quant"].sudo()
        for product_data in raw_data.get("products", []):
            if product_data.get("is_cocktail") or product_data.get("is_spirit_glass"):
                continue
            desired_qty = float(product_data.get("stock") or 0)
            if desired_qty <= 0:
                continue
            product = self.env.ref(
                f"refuge_aventuriers.{product_data['id']}",
                raise_if_not_found=False,
            )
            if not product or product.type != "product":
                continue
            existing_quants = Quant.search([
                ("product_id", "=", product.id),
                ("location_id", "=", location.id),
                ("lot_id", "=", False),
                ("owner_id", "=", False),
                ("package_id", "=", False),
            ])
            current_qty = sum(existing_quants.mapped("quantity"))
            if current_qty > 0:
                continue
            Quant._update_available_quantity(product, location, desired_qty)

    @api.model
    def load_refuge_core_demo(self):
        raw_data = self._load_raw_data()
        self._ensure_loyalty_program_on_pos()
        self._ensure_pos_payment_methods()
        self._seed_partner_activity()
        self._ensure_loyalty_cards(raw_data)
        self._ensure_product_images(raw_data)
        self.env["loyalty.card"].sudo().search([
            ("program_type", "=", "loyalty"),
            ("partner_id", "!=", False),
        ]).refuge_expire_if_needed()
        self._ensure_orderpoints(raw_data)
        self._ensure_stock_quants(raw_data)
        return True
