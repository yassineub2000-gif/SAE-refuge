/** @odoo-module */

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { refugeRpc } from "@refuge_table_order/common/rpc";
import { OrderCard } from "@refuge_table_order/barman/order_card";
import { AppHeader } from "@refuge_aventuriers/theme/app_header";

const POLLING_INTERVAL_MS = 5000;  // ≤ 10 s (cahier des charges §3.5)

export class BarmanApp extends Component {
    static template = "refuge_table_order.BarmanApp";
    static components = { OrderCard, AppHeader };

    setup() {
        this.state = useState({
            orders: [],
            loading: true,
            lastFetchedAt: null,
            error: null,
        });
        this._timer = null;
        onWillStart(() => this.fetchOrders());
        onMounted(() => {
            this._timer = setInterval(() => this.fetchOrders(), POLLING_INTERVAL_MS);
        });
        // Nettoyage du timer à la destruction : sans ça le fetch continue après
        // que le composant quitte le DOM. L'IA l'oublie souvent (cf. Journal IA).
        onWillUnmount(() => {
            if (this._timer) clearInterval(this._timer);
        });
    }

    async fetchOrders() {
        try {
            const data = await refugeRpc("/refuge/api/barman/orders");
            this.state.orders = data.orders || [];
            this.state.lastFetchedAt = data.fetched_at;
            this.state.error = null;
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.loading = false;
        }
    }

    async setStatus(orderId, status) {
        try {
            await refugeRpc("/refuge/api/barman/set_status", { order_id: orderId, status });
            this.state.error = null;
            await this.fetchOrders();
        } catch (e) {
            if (e.message === "not_yours") {
                this.state.error =
                    "Cette commande a été prise par un autre barman — clique sur « Reprendre » pour la récupérer.";
                await this.fetchOrders();
            } else {
                this.state.error = e.message;
            }
        }
    }

    async takeOrder(orderId) {
        try {
            await refugeRpc("/refuge/api/barman/take", { order_id: orderId });
            this.state.error = null;
            await this.fetchOrders();
        } catch (e) {
            this.state.error = e.message;
        }
    }

    async releaseOrder(orderId) {
        try {
            await refugeRpc("/refuge/api/barman/release", { order_id: orderId });
            this.state.error = null;
            await this.fetchOrders();
        } catch (e) {
            this.state.error =
                e.message === "not_yours"
                    ? "Seul le barman en charge peut remettre cette commande en attente."
                    : e.message;
        }
    }

    get grouped() {
        const by = { new: [], in_preparation: [], ready: [] };
        for (const o of this.state.orders) {
            if (by[o.status]) by[o.status].push(o);
        }
        return by;
    }

    get lastFetchedAtLabel() {
        return this.state.lastFetchedAt
            ? new Date(this.state.lastFetchedAt).toLocaleTimeString()
            : "";
    }
}
