/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { refugeRpc } from "@refuge_table_order/common/rpc";
import { AppHeader } from "@refuge_aventuriers/theme/app_header";

/**
 * App tablette « Clients » : recherche, consultation des points fidélité et
 * de l'historique de commandes, édition des coordonnées (nom / tél / email).
 * Les points fidélité sont en lecture seule (intégrité du programme).
 */
export class ClientsApp extends Component {
    static template = "refuge_table_order.ClientsApp";
    static components = { AppHeader };

    setup() {
        this.state = useState({
            query: "",
            results: [],
            loading: false,
            selected: null,    // fiche complète {client, history}
            edit: null,        // brouillon d'édition {name, phone, email}
            saving: false,
            error: null,
            savedFlash: false,
        });
        this._searchTimer = null;
        onWillStart(() => this.runSearch());
    }

    onInput(ev) {
        this.state.query = ev.target.value;
        clearTimeout(this._searchTimer);
        this._searchTimer = setTimeout(() => this.runSearch(), 250);
    }

    async runSearch() {
        this.state.loading = true;
        try {
            const res = await refugeRpc("/refuge/api/clients/search", {
                query: this.state.query,
            });
            this.state.results = res.clients || [];
            this.state.error = null;
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.loading = false;
        }
    }

    async open(partnerId) {
        this.state.error = null;
        this.state.savedFlash = false;
        try {
            const res = await refugeRpc("/refuge/api/clients/detail", {
                partner_id: partnerId,
            });
            this.state.selected = res;
            this.state.edit = null;
        } catch (e) {
            this.state.error = e.message;
        }
    }

    closeDetail() {
        this.state.selected = null;
        this.state.edit = null;
    }

    startEdit() {
        const c = this.state.selected.client;
        this.state.edit = { name: c.name, phone: c.phone, email: c.email };
        this.state.error = null;
    }

    cancelEdit() {
        this.state.edit = null;
    }

    updateField(field, ev) {
        this.state.edit[field] = ev.target.value;
    }

    async save() {
        if (this.state.saving) return;
        if (!this.state.edit.name.trim()) {
            this.state.error = "Le nom est obligatoire.";
            return;
        }
        this.state.saving = true;
        try {
            const res = await refugeRpc("/refuge/api/clients/update", {
                partner_id: this.state.selected.client.id,
                name: this.state.edit.name,
                phone: this.state.edit.phone,
                email: this.state.edit.email,
            });
            this.state.selected.client = res.client;
            this.state.edit = null;
            this.state.error = null;
            this.state.savedFlash = true;
            // Reflète le changement dans la liste de résultats.
            const row = this.state.results.find(
                (r) => r.id === res.client.id);
            if (row) {
                row.name = res.client.name;
                row.phone = res.client.phone;
                row.email = res.client.email;
            }
        } catch (e) {
            this.state.error =
                e.message === "name_required"
                    ? "Le nom est obligatoire."
                    : e.message;
        } finally {
            this.state.saving = false;
        }
    }

    fmtDate(iso) {
        if (!iso) return "";
        const d = new Date(iso);
        return d.toLocaleDateString() + " " + d.toLocaleTimeString(
            [], { hour: "2-digit", minute: "2-digit" });
    }

    fmtAmount(v) {
        return (v || 0).toFixed(2) + " €";
    }

    sourceLabel(src) {
        return src === "qr" ? "Table (QR)" : "Comptoir";
    }
}
