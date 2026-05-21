from . import models

_REFUGE_STAFF_LOGINS = (
    "corentin.leblanc@refuge-aventuriers.fr",
    "marlene.dupont@refuge-aventuriers.fr",
    "anthony.faure@refuge-aventuriers.fr",
    "julie.perrin@refuge-aventuriers.fr",
)


def post_init_refuge_staff(env):
    """À l'installation : pose le mot de passe commun par défaut des comptes
    Staff et rattache les fiches employé. Volontairement exécuté seulement à
    l'install (pas sur -u) pour ne jamais réinitialiser un mot de passe que
    le gérant aurait changé en production."""
    users = env["res.users"].sudo().search(
        [("login", "in", list(_REFUGE_STAFF_LOGINS))])
    for user in users:
        user.password = "refuge"
    env["hr.employee"].sudo()._refuge_link_staff_users()
