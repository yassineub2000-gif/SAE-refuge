/** @odoo-module */

import { Component, useState, onWillStart, onMounted, onWillUnmount } from "@odoo/owl";
import { refugeRpc } from "@refuge_table_order/common/rpc";
import { OrderCard } from "@refuge_table_order/barman/order_card";
import { PartnerPicker } from "@refuge_table_order/barman/partner_picker";

const POLLING_INTERVAL_MS = 5000;  // ≤ 10 s (cahier des charges §3.5)

export class BarmanApp extends Component {
    static template = "refuge_table_order.BarmanApp";
    static components = { OrderCard, PartnerPicker };

    setup() {
        this.state = useState({
            orders: [],
            loading: true,
            lastFetchedAt: null,
            error: null,
            pickerOrder: null,  // commande pour laquelle on ouvre la modale client
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
            await this.fetchOrders();
        } catch (e) {
            this.state.error = e.message;
        }
    }

    get grouped() {
        const by = { new: [], in_preparation: [], ready: [] };
        for (const o of this.state.orders) {
            if (by[o.status]) by[o.status].push(o);
        }
        return by;
    }

    openPartnerPicker(order) {
        this.state.pickerOrder = order;
    }
    closePartnerPicker() {
        this.state.pickerOrder = null;
    }

    get lastFetchedAtLabel() {
        return this.state.lastFetchedAt
            ? new Date(this.state.lastFetchedAt).toLocaleTimeString()
            : "";
    }
}
