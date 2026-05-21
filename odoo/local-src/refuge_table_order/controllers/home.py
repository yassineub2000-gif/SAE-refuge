"""Verrouillage back-office pour les comptes Staff (tablette).

Les employés sont des utilisateurs internes (pour pouvoir lire/écrire
pos.order, res.partner, planning via les apps OWL) mais ne doivent jamais
voir le back-office Odoo : toute arrivée sur '/' ou '/web' les renvoie vers
l'accueil tablette '/refuge'. L'admin et les utilisateurs système ne sont
jamais redirigés.
"""

from odoo import http
from odoo.http import request
from odoo.addons.web.controllers.home import Home


class RefugeHome(Home):

    def _refuge_staff_redirect(self):
        """Retourne une redirection vers /refuge si l'utilisateur courant est
        un membre Staff sans privilège back-office, sinon None."""
        try:
            if not request.db or not request.session.uid:
                return None
            request.update_env(user=request.session.uid)
            user = request.env.user
            if user._is_admin() or user._is_system():
                return None
            if user.has_group("refuge_aventuriers.group_refuge_staff"):
                return request.redirect("/refuge")
        except Exception:  # noqa: BLE001 — ne jamais casser le login
            return None
        return None

    @http.route()
    def index(self, *args, **kw):
        return self._refuge_staff_redirect() or super().index(*args, **kw)

    @http.route()
    def web_client(self, *args, **kw):
        return self._refuge_staff_redirect() or super().web_client(*args, **kw)
