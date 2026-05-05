/** @odoo-module */

import { App, whenReady } from "@odoo/owl";
import { templates } from "@web/core/assets";
import { makeEnv, startServices } from "@web/env";
import { PlanningApp } from "@refuge_planning/planning_app";

(async function bootPlanning() {
    await whenReady();
    const env = makeEnv();
    await startServices(env);
    const app = new App(PlanningApp, {
        name: "Refuge — Planning",
        env,
        templates,
        dev: env.debug,
        warnIfNoStaticProps: true,
    });
    await app.mount(document.getElementById("refuge-planning-root"));
})();
