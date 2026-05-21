/** @odoo-module */

import { Component } from "@odoo/owl";

export class MenuScreen extends Component {
    static template = "refuge_table_order.MenuScreen";
    static props = {
        categories: Array,
        cart: Array,
        onAdd: Function,
        onChangeQty: Function,
        onRemove: Function,
    };

    /** Quantité actuelle de ce produit dans le panier (0 si absent). */
    qtyOf(productId) {
        const line = this.props.cart.find((l) => l.product_id === productId);
        return line ? line.qty : 0;
    }

    /** « − » : retire la ligne si on tombe à 0, sinon décrémente. */
    decrement(productId) {
        if (this.qtyOf(productId) <= 1) {
            this.props.onRemove(productId);
        } else {
            this.props.onChangeQty(productId, -1);
        }
    }

    /** Identifiant DOM stable pour une catégorie. Les regex ne passent pas
     *  dans les expressions inline OWL (le tokenizer lève "could not tokenize"),
     *  on calcule donc le slug en JS. */
    categoryId(name) {
        return "cat-" + String(name).replace(/\s+/g, "-").replace(/[^a-zA-Z0-9_-]/g, "");
    }

    scrollToCategory(name) {
        const el = document.getElementById(this.categoryId(name));
        if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}
