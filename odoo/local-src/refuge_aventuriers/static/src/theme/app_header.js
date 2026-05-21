/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { currentTheme, toggleTheme } from "@refuge_aventuriers/theme/theme";

/**
 * En-tête unifié de toutes les apps tablette/staff.
 * Flèche retour (← accueil), titre + sous-titre, et à droite : nom de
 * l'utilisateur, switch de thème ☀️/🌙, déconnexion.
 */
export class AppHeader extends Component {
    static template = "refuge_aventuriers.AppHeader";
    static props = {
        title: String,
        subtitle: { type: String, optional: true },
        backHref: { type: String, optional: true },
        showBack: { type: Boolean, optional: true },
        userName: { type: String, optional: true },
        showLogout: { type: Boolean, optional: true },
    };

    setup() {
        this.ui = useState({ theme: currentTheme() });
    }

    get backHref() {
        return this.props.backHref || "/refuge";
    }

    toggleTheme() {
        this.ui.theme = toggleTheme();
    }
}
