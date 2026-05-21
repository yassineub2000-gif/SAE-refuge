/** @odoo-module */

import { App, whenReady } from "@odoo/owl";
import { templates } from "@web/core/assets";
import { makeEnv, startServices } from "@web/env";
import { ClientsApp } from "@refuge_table_order/clients/clients_app";

(async function bootClients() {
    await whenReady();
    const env = makeEnv();
    await startServices(env);
    const app = new App(ClientsApp, {
        name: "Refuge — Clients",
        env,
        templates,
        dev: env.debug,
        warnIfNoStaticProps: true,
    });
    await app.mount(document.getElementById("refuge-root"));
})();
