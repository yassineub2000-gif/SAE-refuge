/** @odoo-module */

import { Component } from "@odoo/owl";

export class CartScreen extends Component {
    static template = "refuge_table_order.CartScreen";
    static props = {
        cart: Array,
        total: Number,
        onChangeQty: Function,
        onRemove: Function,
        onSubmit: Function,
    };
}
