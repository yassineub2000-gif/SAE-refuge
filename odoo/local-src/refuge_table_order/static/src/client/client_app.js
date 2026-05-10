/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { refugeRpc } from "@refuge_table_order/common/rpc";
import { MenuScreen } from "@refuge_table_order/client/menu_screen";
import { CartScreen } from "@refuge_table_order/client/cart_screen";
import { ConfirmScreen } from "@refuge_table_order/client/confirm_screen";
import { AuthScreen } from "@refuge_table_order/client/auth_screen";

/**
 * Racine de l'application client (commande sur table).
 * Gère la navigation entre les écrans (menu / auth / panier / confirmation),
 * détient le store du panier et l'éventuel partner connecté.
 */
export class ClientApp extends Component {
    static template = "refuge_table_order.ClientApp";
    static components = { MenuScreen, CartScreen, ConfirmScreen, AuthScreen };

    setup() {
        const table = window.REFUGE_TABLE || { token: "", number: "?", label: "" };
        this.state = useState({
            // L'écran d'auth est l'entrée par défaut : on demande au client
            // s'il a un compte, veut en créer un, ou continue en invité, avant
            // d'afficher la carte.
            screen: "auth",  // "auth" | "menu" | "cart" | "confirm"
            table,
            categories: [],
            loading: true,
            error: null,
            cart: [],  // [{ product_id, name, price, qty }]
            lastReference: null,
            partner: null,   // { id, name, email, points, tiers[] } si connecté
            useTier: null,   // 50 | 100 | 200 — palier sélectionné par le client
        });
        onWillStart(async () => {
            try {
                const data = await refugeRpc(
                    `/refuge/api/table/${encodeURIComponent(table.token)}/menu`,
                );
                this.state.categories = data.categories || [];
            } catch (e) {
                this.state.error = e.message;
            } finally {
                this.state.loading = false;
            }
        });
    }

    addToCart(product) {
        const existing = this.state.cart.find((l) => l.product_id === product.id);
        if (existing) {
            existing.qty += 1;
        } else {
            this.state.cart.push({
                product_id: product.id,
                name: product.name,
                price: product.price,
                qty: 1,
            });
        }
    }
    removeFromCart(productId) {
        this.state.cart = this.state.cart.filter((l) => l.product_id !== productId);
    }
    changeQty(productId, delta) {
        const line = this.state.cart.find((l) => l.product_id === productId);
        if (!line) return;
        line.qty = Math.max(1, line.qty + delta);
    }
    get cartTotal() {
        return this.state.cart.reduce((s, l) => s + l.price * l.qty, 0);
    }
    get cartCount() {
        return this.state.cart.reduce((s, l) => s + l.qty, 0);
    }

    /** Réduction en € si le client a sélectionné un palier fidélité. */
    get loyaltyDiscount() {
        const tier = this.state.useTier && this.state.partner
            ? this.state.partner.tiers.find((t) => t.points === this.state.useTier)
            : null;
        if (!tier) return 0;
        if (tier.kind === "percent") return +(this.cartTotal * tier.value / 100).toFixed(2);
        return Math.min(tier.value, this.cartTotal);
    }
    get cartFinal() { return Math.max(0, this.cartTotal - this.loyaltyDiscount); }

    /** Navigation : "cart" force le passage par l'écran d'auth si invité. */
    goto(screen) {
        if (screen === "cart" && !this.state.partner && this.state.skipAuth !== true) {
            this.state.screen = "auth";
            return;
        }
        this.state.screen = screen;
    }
    onAuthenticated(partner) {
        this.state.partner = partner;
        this.state.skipAuth = true;
        // Si le panier contient déjà des articles, on file directement à la
        // validation ; sinon on ouvre la carte pour que le client choisisse.
        this.state.screen = this.state.cart.length ? "cart" : "menu";
    }
    onGuest() {
        this.state.skipAuth = true;
        this.state.screen = this.state.cart.length ? "cart" : "menu";
    }
    setTier(points) {
        // Toggle : re-cliquer sur le même palier désélectionne.
        this.state.useTier = this.state.useTier === points ? null : points;
    }
    logout() {
        this.state.partner = null;
        this.state.useTier = null;
        this.state.skipAuth = false;
    }

    async submitOrder() {
        try {
            const payload = {
                lines: this.state.cart.map((l) => ({ product_id: l.product_id, qty: l.qty })),
            };
            if (this.state.partner) {
                payload.partner_id = this.state.partner.id;
                payload.pin = this.state.partner.pin;  // injecté à l'auth
                if (this.state.useTier) payload.use_tier = this.state.useTier;
            }
            const res = await refugeRpc(
                `/refuge/api/table/${encodeURIComponent(this.state.table.token)}/submit`,
                payload,
            );
            if (res.error) { this.state.error = res.error; return; }
            this.state.lastReference = res.reference;
            if (this.state.partner && typeof res.points_balance === "number") {
                this.state.partner.points = res.points_balance;
            }
            this.state.cart = [];
            this.state.useTier = null;
            this.state.screen = "confirm";
        } catch (e) {
            this.state.error = e.message;
        }
    }
}
