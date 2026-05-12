/** @odoo-module */

import { App, whenReady } from "@odoo/owl";
import { templates } from "@web/core/assets";
import { makeEnv, startServices } from "@web/env";
import { BarmanApp } from "@refuge_table_order/barman/barman_app";

(async function bootBarman() {
    await whenReady();
    const env = makeEnv();
    await startServices(env);
    const app = new App(BarmanApp, {
        name: "Refuge — Espace barman",
        env,
        templates,
        dev: env.debug,
        warnIfNoStaticProps: true,
    });
    await app.mount(document.getElementById("refuge-root"));
})();
