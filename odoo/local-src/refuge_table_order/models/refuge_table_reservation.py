from datetime import timedelta

from odoo import api, fields, models


class RefugeTableReservation(models.Model):
    _name = "refuge.table.reservation"
    _description = "Reservation de table"
    _order = "reservation_datetime desc, id desc"

    name = fields.Char(string="Reference", required=True, default="Nouvelle reservation")
    partner_id = fields.Many2one(
        "res.partner",
        string="Client",
        ondelete="set null",
        index=True,
    )
    phone = fields.Char(string="Telephone")
    table_id = fields.Many2one(
        "refuge.table",
        string="Table",
        required=True,
        ondelete="restrict",
        index=True,
    )
    reservation_datetime = fields.Datetime(string="Date / heure", required=True, index=True)
    party_size = fields.Integer(string="Nombre de personnes", default=2, required=True)
    status = fields.Selection(
        [
            ("confirmed", "Confirmee"),
            ("seated", "Installee"),
            ("completed", "Terminee"),
            ("cancelled", "Annulee"),
        ],
        string="Statut",
        default="confirmed",
        required=True,
        index=True,
    )
    notes = fields.Text(string="Notes")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            partner = self.env["res.partner"].browse(vals.get("partner_id")).exists()
            if partner and not vals.get("phone"):
                vals["phone"] = partner.phone
            if not vals.get("name") or vals["name"] == "Nouvelle reservation":
                when = fields.Datetime.to_datetime(vals.get("reservation_datetime")) or fields.Datetime.now()
                table = self.env["refuge.table"].browse(vals.get("table_id")).exists()
                table_label = table.number or "?"
                vals["name"] = f"RES-{when:%Y%m%d-%H%M}-T{table_label}"
        return super().create(vals_list)

    @api.model
    def load_demo_reservations(self):
        Reservation = self.sudo()
        today = fields.Datetime.to_datetime(fields.Datetime.now())
        horizon_end = today + timedelta(days=7)
        if Reservation.search_count([
            ("reservation_datetime", ">=", today),
            ("reservation_datetime", "<=", horizon_end),
        ]):
            return True

        demo_rows = [
            ("refuge_aventuriers.partner_cli_jean_martin", "refuge_table_order.table_1", 1, 19, 30, 4, "confirmed", "Anniversaire, table calme si possible."),
            ("refuge_aventuriers.partner_cli_sophie_durand", "refuge_table_order.table_2", 2, 18, 45, 2, "confirmed", "Passage rapide avant concert."),
            ("refuge_aventuriers.partner_cli_aurore_michel", "refuge_table_order.table_3", 3, 20, 15, 5, "seated", "Cliente reguliere, aime les cocktails signature."),
        ]
        for partner_xmlid, table_xmlid, day_offset, hour, minute, party_size, status, notes in demo_rows:
            partner = self.env.ref(partner_xmlid, raise_if_not_found=False)
            table = self.env.ref(table_xmlid, raise_if_not_found=False)
            if not partner or not table:
                continue
            reservation_dt = today.replace(hour=hour, minute=minute, second=0, microsecond=0) + timedelta(days=day_offset)
            existing = Reservation.search([
                ("partner_id", "=", partner.id),
                ("table_id", "=", table.id),
                ("reservation_datetime", "=", reservation_dt),
            ], limit=1)
            if existing:
                continue
            Reservation.create({
                "partner_id": partner.id,
                "table_id": table.id,
                "reservation_datetime": reservation_dt,
                "party_size": party_size,
                "status": status,
                "notes": notes,
            })
        return True
