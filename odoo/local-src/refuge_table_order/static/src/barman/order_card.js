/** @odoo-module */

import { Component, useState, onMounted, onWillUnmount } from "@odoo/owl";

const STEP_BUDGET_MS = 5 * 60 * 1000;  // 5 min par étape (toutes colonnes)

export class OrderCard extends Component {
    static template = "refuge_table_order.OrderCard";
    static props = {
        order: Object,
        onNext: Function,
        nextLabel: String,
        onTake: Function,
        onRelease: { type: Function, optional: true },
    };

    setup() {
        // Horloge locale qui tique chaque seconde pour le compte à rebours.
        this.clock = useState({ now: Date.now() });
        this._timer = null;
        onMounted(() => {
            this._timer = setInterval(() => {
                this.clock.now = Date.now();
            }, 1000);
        });
        onWillUnmount(() => {
            if (this._timer) clearInterval(this._timer);
        });
    }

    get createdAt() {
        return this.props.order.created
            ? new Date(this.props.order.created).toLocaleTimeString()
            : "";
    }

    /** Client identifié (connecté) vs invité (commande anonyme par QR). */
    get isGuest() {
        return !this.props.order.partner_name;
    }

    /** Commande déjà prise en charge par un barman. */
    get isAssigned() {
        return !!this.props.order.assignee_id;
    }

    /** Prise en charge par le barman connecté. */
    get isMine() {
        return !!this.props.order.is_mine;
    }

    /**
     * Le barman courant peut faire avancer la commande si :
     *  - elle est encore Nouvelle (non assignée — il la prend),
     *  - ou elle est déjà à lui.
     */
    get canAdvance() {
        return !this.isAssigned || this.isMine;
    }

    /** Bouton « Remettre en nouvelle » dispo (colonnes En prép./Prête, à moi). */
    get canRelease() {
        return !!this.props.onRelease && this.isMine;
    }

    // ----------------------------------------------------------- timer 5 min

    /** Millisecondes restantes sur le budget de 5 min de l'étape courante. */
    get remainingMs() {
        const since = this.props.order.status_since;
        if (!since) return null;
        const target = Date.parse(since) + STEP_BUDGET_MS;
        return target - this.clock.now;
    }

    /** Libellé mm:ss ; figé à 00:00 une fois les 5 min dépassées. */
    get timerLabel() {
        const r = this.remainingMs;
        if (r === null) return "";
        if (r <= 0) return "00:00";
        const total = Math.floor(r / 1000);
        const m = Math.floor(total / 60);
        const s = total % 60;
        return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    }

    /** Couleur : vert > 1 min, rouge ≤ 1 min, rouge "dépassé" si ≤ 0. */
    get timerClass() {
        const r = this.remainingMs;
        if (r === null) return "";
        if (r <= 0) return "is-over";
        if (r <= 60000) return "is-warn";
        return "is-ok";
    }

    // ------------------------------------------------------------ stock badge

    /** Affiche le stock sans décimales inutiles (37.0 → 37, 5.9 → 5.9). */
    fmtStock(qty) {
        return Number.isInteger(qty) ? String(qty) : qty.toFixed(1);
    }

    /**
     * Couleur du badge stock : rouge si épuisé ou insuffisant pour la
     * quantité commandée, ambre si stock faible, vert sinon.
     */
    stockClass(line) {
        const stock = line.qty_available;
        if (stock <= 0 || stock < line.qty) return "is-out";
        if (stock < line.qty * 3) return "is-low";
        return "is-ok";
    }
}
