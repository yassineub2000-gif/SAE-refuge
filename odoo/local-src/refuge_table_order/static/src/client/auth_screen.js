/** @odoo-module */

import { Component, useState } from "@odoo/owl";
import { refugeRpc } from "@refuge_table_order/common/rpc";

/**
 * Écran intermédiaire affiché quand le client clique sur "Panier" sans être
 * identifié. Propose trois chemins : se connecter, créer un compte ou
 * continuer en invité. La connexion / création utilise un PIN à 4-6 chiffres.
 */
export class AuthScreen extends Component {
    static template = "refuge_table_order.AuthScreen";
    static props = {
        tableToken: String,
        onAuthenticated: Function,  // (partner) => void
        onGuest: Function,
        onBack: Function,
    };

    setup() {
        this.state = useState({
            mode: "choice", // "choice" | "login" | "signup"
            email: "",
            name: "",
            pin: "",
            error: null,
            loading: false,
        });
    }

    show(mode) {
        this.state.mode = mode;
        this.state.error = null;
    }

    async submit() {
        if (this.state.loading) return;
        this.state.loading = true;
        this.state.error = null;
        try {
            const path = this.state.mode === "login" ? "auth/login" : "auth/signup";
            const payload = {
                email: this.state.email.trim(),
                pin: this.state.pin.trim(),
            };
            if (this.state.mode === "signup") payload.name = this.state.name.trim();
            const res = await refugeRpc(
                `/refuge/api/table/${encodeURIComponent(this.props.tableToken)}/${path}`,
                payload,
            );
            if (res.error) {
                this.state.error = this._humanError(res.error);
                return;
            }
            // On stocke le PIN côté client pour ré-authentifier la commande à l'envoi.
            this.props.onAuthenticated({ ...res.partner, pin: this.state.pin.trim() });
        } catch (e) {
            this.state.error = e.message || "Erreur réseau";
        } finally {
            this.state.loading = false;
        }
    }

    _humanError(code) {
        return {
            missing_credentials: "Email et code requis.",
            missing_fields: "Tous les champs sont obligatoires.",
            invalid_credentials: "Email ou code incorrect.",
            email_exists: "Cet email est déjà inscrit. Utilisez « J'ai un compte ».",
        }[code] || `Erreur : ${code}`;
    }
}
