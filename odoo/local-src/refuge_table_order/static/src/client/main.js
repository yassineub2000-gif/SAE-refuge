/** @odoo-module */

import { App, whenReady } from "@odoo/owl";
import { templates } from "@web/core/assets";
import { makeEnv, startServices } from "@web/env";
import { ClientApp } from "@refuge_table_order/client/client_app";

(async function bootClient() {
    await whenReady();
    const env = makeEnv();
    await startServices(env);
    const app = new App(ClientApp, {
        name: "Refuge — Commande Table",
        env,
        templates,
        dev: env.debug,
        warnIfNoStaticProps: true,
    });
    await app.mount(document.getElementById("refuge-root"));
})();
