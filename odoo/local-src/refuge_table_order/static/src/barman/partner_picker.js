/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { refugeRpc } from "@refuge_table_order/common/rpc";

/**
 * Modale / popover permettant au barman de :
 *  - rechercher un client existant (autocomplete sur nom/email/téléphone)
 *  - créer un nouveau client si inconnu
 *  - l'attacher à une commande QR pour créditer la fidélité et garder la trace
 *    de qui a commandé (utile pour retrouver une commande sans ticket).
 */
export class PartnerPicker extends Component {
    static template = "refuge_table_order.PartnerPicker";
    static props = {
        order: Object,
        onAttached: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({
            query: "",
            results: [],
            searching: false,
            error: null,
            creating: false,
            newPartner: { name: "", email: "", phone: "" },
        });
    }

    async doSearch() {
        this.state.searching = true;
        try {
            const res = await refugeRpc("/refuge/api/barman/partners/search", {
                query: this.state.query,
            });
            this.state.results = res.partners || [];
            this.state.error = null;
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.searching = false;
        }
    }

    updateQuery(ev) {
        this.state.query = ev.target.value;
        this.doSearch();
    }

    updateNew(field, ev) {
        this.state.newPartner[field] = ev.target.value;
    }

    async attach(partnerId) {
        try {
            await refugeRpc("/refuge/api/barman/orders/attach_partner", {
                order_id: this.props.order.id,
                partner_id: partnerId,
            });
            this.props.onAttached();
            this.props.onClose();
        } catch (e) {
            this.state.error = e.message;
        }
    }

    async createAndAttach() {
        if (!this.state.newPartner.name.trim()) {
            this.state.error = "Le nom est requis.";
            return;
        }
        this.state.creating = true;
        try {
            const created = await refugeRpc("/refuge/api/barman/partners/create",
                                            this.state.newPartner);
            await this.attach(created.id);
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.creating = false;
        }
    }
}
