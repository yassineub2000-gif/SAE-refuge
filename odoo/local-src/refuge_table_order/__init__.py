from . import models
from . import controllers

from odoo import api, SUPERUSER_ID


def post_init_sync_qr_menus(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    env["refuge.table"].search([("menu_id", "=", False)])._sync_qr_menu()
