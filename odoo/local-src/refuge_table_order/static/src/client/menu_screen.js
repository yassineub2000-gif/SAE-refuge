/** @odoo-module */

import { Component } from "@odoo/owl";

export class MenuScreen extends Component {
    static template = "refuge_table_order.MenuScreen";
    static props = {
        categories: Array,
        onAdd: Function,
    };

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
