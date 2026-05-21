/** @odoo-module */

import { Component, onWillStart, useState } from "@odoo/owl";
import { refugeRpc } from "@refuge_table_order/common/rpc";
import { AppHeader } from "@refuge_aventuriers/theme/app_header";

export class QrAdminApp extends Component {
    static template = "refuge_table_order.QrAdminApp";
    static components = { AppHeader };

    setup() {
        this.state = useState({
            loading: true,
            rotating: false,
            error: null,
            flash: "",
            query: "",
            baseUrl: "",
            baseUrlWarning: "",
            ngrokCommand: "",
            tables: [],
            selectedIds: [],
        });
        onWillStart(() => this.load());
    }

    get filteredTables() {
        const query = this.state.query.trim().toLowerCase();
        if (!query) {
            return this.state.tables;
        }
        return this.state.tables.filter((table) => {
            const haystack = [
                table.number,
                table.name,
                table.restaurant_table_name,
                table.qr_url,
            ].join(" ").toLowerCase();
            return haystack.includes(query);
        });
    }

    get selectedCount() {
        return this.state.selectedIds.length;
    }

    isSelected(tableId) {
        return this.state.selectedIds.includes(tableId);
    }

    async load() {
        this.state.loading = true;
        try {
            const res = await refugeRpc("/refuge/api/admin/qr/state", {});
            this.state.baseUrl = res.base_url || "";
            this.state.baseUrlWarning = res.base_url_warning || "";
            this.state.ngrokCommand = res.ngrok_command || "";
            this.state.tables = res.tables || [];
            this.state.selectedIds = this.state.tables.map((table) => table.id);
            this.state.error = null;
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.loading = false;
        }
    }

    setQuery(ev) {
        this.state.query = ev.target.value;
    }

    toggleSelection(tableId) {
        if (this.isSelected(tableId)) {
            this.state.selectedIds = this.state.selectedIds.filter((id) => id !== tableId);
        } else {
            this.state.selectedIds = [...this.state.selectedIds, tableId];
        }
    }

    selectFiltered() {
        const ids = new Set(this.state.selectedIds);
        for (const table of this.filteredTables) {
            ids.add(table.id);
        }
        this.state.selectedIds = [...ids];
    }

    clearSelection() {
        this.state.selectedIds = [];
    }

    selectAll() {
        this.state.selectedIds = this.state.tables.map((table) => table.id);
    }

    openTable(table) {
        window.open(table.qr_url, "_blank", "noopener");
    }

    printSelection() {
        const ids = this.state.selectedIds.length
            ? this.state.selectedIds
            : this.filteredTables.map((table) => table.id);
        const url = `/refuge/admin/qr/print?ids=${ids.join(",")}`;
        window.open(url, "_blank", "noopener");
    }

    printSingle(table) {
        window.open(`/refuge/admin/qr/print?ids=${table.id}`, "_blank", "noopener");
    }

    async copyUrl(table) {
        try {
            await navigator.clipboard.writeText(table.qr_url);
            this.flash(`Lien de la table ${table.number} copié.`);
        } catch {
            this.state.error = "Impossible de copier automatiquement le lien.";
        }
    }

    async rotateSelection() {
        const ids = this.state.selectedIds.length
            ? this.state.selectedIds
            : this.filteredTables.map((table) => table.id);
        if (!ids.length) {
            this.state.error = "Aucune table sélectionnée.";
            return;
        }
        if (!window.confirm(`Régénérer le QR code pour ${ids.length} table(s) ? Les anciens QR seront invalides.`)) {
            return;
        }
        this.state.rotating = true;
        try {
            await refugeRpc("/refuge/api/admin/qr/rotate", { table_ids: ids });
            await this.load();
            this.flash(`${ids.length} table(s) régénérée(s).`);
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.rotating = false;
        }
    }

    async rotateSingle(table) {
        if (!window.confirm(`Régénérer le QR code de la table ${table.number} ?`)) {
            return;
        }
        this.state.rotating = true;
        try {
            await refugeRpc("/refuge/api/admin/qr/rotate", { table_ids: [table.id] });
            await this.load();
            this.flash(`QR de la table ${table.number} régénéré.`);
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.rotating = false;
        }
    }

    flash(message) {
        this.state.flash = message;
        window.clearTimeout(this._flashTimer);
        this._flashTimer = window.setTimeout(() => {
            this.state.flash = "";
        }, 2200);
    }
}
