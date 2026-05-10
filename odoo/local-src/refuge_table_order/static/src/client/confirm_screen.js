/** @odoo-module */

import { Component } from "@odoo/owl";

export class ConfirmScreen extends Component {
    static template = "refuge_table_order.ConfirmScreen";
    static props = {
        reference: { type: String, optional: true },
        onNewOrder: Function,
    };
}
