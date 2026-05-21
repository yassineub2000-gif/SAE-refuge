import pytz

from odoo import api, fields, models


class PosConfig(models.Model):
    _inherit = "pos.config"

    @api.depends("session_ids")
    def _compute_last_session(self):
        """Rend le tableau de bord POS tolérant aux sessions fermées incomplètes.

        Odoo suppose qu'une session `closed` possède toujours un `stop_at`.
        Or une base de démo ou un arrêt brutal peut laisser une session fermée
        avec `stop_at = False`, ce qui casse la lecture du POS.
        """
        PosSession = self.env["pos.session"]
        timezone = pytz.timezone(self._context.get("tz") or self.env.user.tz or "UTC")
        for pos_config in self:
            session = PosSession.search_read(
                [("config_id", "=", pos_config.id), ("state", "=", "closed")],
                ["cash_register_balance_end_real", "stop_at", "start_at"],
                order="stop_at desc, start_at desc, id desc",
                limit=1,
            )
            if session:
                stop_at = session[0]["stop_at"] or session[0]["start_at"]
                pos_config.last_session_closing_cash = session[0]["cash_register_balance_end_real"]
                pos_config.last_session_closing_date = (
                    stop_at.astimezone(timezone).date() if stop_at else False
                )
            else:
                pos_config.last_session_closing_cash = 0
                pos_config.last_session_closing_date = False
