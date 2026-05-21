from . import models
from . import controllers

from odoo import api, SUPERUSER_ID


def post_init_sync_qr_menus(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})
    tables = env["refuge.table"].search([])
    tables.filtered(lambda table: not table.menu_id)._sync_qr_menu()
    tables.sync_pos_restaurant_memory()
    env["pos.order"].normalize_refuge_pos_references()
    env["pos.order"].cleanup_refuge_table_drafts()
