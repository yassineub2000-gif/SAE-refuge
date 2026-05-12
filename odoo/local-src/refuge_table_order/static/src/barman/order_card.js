/** @odoo-module */

import { Component } from "@odoo/owl";

export class OrderCard extends Component {
    static template = "refuge_table_order.OrderCard";
    static props = {
        order: Object,
        onNext: Function,
        nextLabel: String,
        onAttachPartner: Function,
    };

    get createdAt() {
        return this.props.order.created
            ? new Date(this.props.order.created).toLocaleTimeString()
            : "";
    }
}
