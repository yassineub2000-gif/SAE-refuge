/** @odoo-module */

import { mount } from "@odoo/owl";
import { whenReady } from "@odoo/owl";
import { QrAdminApp } from "@refuge_table_order/admin/qr_admin_app";

whenReady(() => {
    mount(QrAdminApp, document.getElementById("refuge-root"));
});
