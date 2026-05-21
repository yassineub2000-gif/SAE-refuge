from odoo import api, fields, models


# Disponibilités par défaut (spec officielle du fichier client). Pour chaque
# employé, liste de (weekday, status, pref_start, pref_end) ; un jour absent
# de la liste est marqué `unavailable` (plage par défaut 10-25 sans effet).
# Convention horaire : 24.0 = minuit, 25.0 = 01h du lendemain (ouverture bar).
# Utilisé à l'install ET par le bouton « Réinitialiser au défaut ».
_REFUGE_DEFAULT_AVAILABILITY = {
    # Corentin Leblanc — Mar-Sam, préférence 10h-18h
    "refuge_aventuriers.emp_pierre_leblanc": [
        ("1", "available", 10.0, 18.0),
        ("2", "available", 10.0, 18.0),
        ("3", "available", 10.0, 18.0),
        ("4", "available", 10.0, 18.0),
        ("5", "available", 10.0, 18.0),
    ],
    # Marlène Dupont — Mer-Dim, préférence 18h-01h
    "refuge_aventuriers.emp_marlene_dupont": [
        ("2", "available", 18.0, 25.0),
        ("3", "available", 18.0, 25.0),
        ("4", "available", 18.0, 25.0),
        ("5", "available", 18.0, 25.0),
        ("6", "available", 18.0, 25.0),
    ],
    # Anthony Faure — Mar + Jeu-Dim, flexible (toute l'amplitude)
    "refuge_aventuriers.emp_anthony_faure": [
        ("1", "available", 10.0, 25.0),
        ("3", "available", 10.0, 25.0),
        ("4", "available", 10.0, 25.0),
        ("5", "available", 10.0, 25.0),
        ("6", "available", 10.0, 25.0),
    ],
    # Julie Perrin — Mer + Ven-Dim, « Après 16h » (16h-01h)
    "refuge_aventuriers.emp_julie_perrin": [
        ("2", "available", 16.0, 25.0),
        ("4", "available", 16.0, 25.0),
        ("5", "available", 16.0, 25.0),
        ("6", "available", 16.0, 25.0),
    ],
}

# Représentation du tableau de disponibilités du fichier Excel fourni
# (feuille « Disponibilités Planning »).
# 0 = Lundi … 6 = Dimanche — conforme à la convention Python datetime.weekday().

WEEKDAYS = [
    ("0", "Lundi"),
    ("1", "Mardi"),
    ("2", "Mercredi"),
    ("3", "Jeudi"),
    ("4", "Vendredi"),
    ("5", "Samedi"),
    ("6", "Dimanche"),
]

AVAILABILITY = [
    ("available", "Disponible"),
    ("unavailable", "Indisponible"),
]


class RefugeAvailability(models.Model):
    """Disponibilité hebdomadaire d'un employé pour un jour donné.

    Sert d'entrée à l'algorithme de génération automatique du planning.
    Le fichier Excel fourni par le client est importé lors de l'installation
    du module (data/refuge_availability_data.xml).
    """

    _name = "refuge.planning.availability"
    _description = "Disponibilité employé (hebdo)"
    _rec_name = "employee_id"
    _order = "employee_id, weekday"

    employee_id = fields.Many2one(
        "hr.employee", string="Employé", required=True, ondelete="cascade", index=True,
    )
    weekday = fields.Selection(WEEKDAYS, string="Jour", required=True)
    status = fields.Selection(
        AVAILABILITY, string="Disponibilité", required=True, default="available",
    )
    # Plage horaire préférée par jour (slider double poignée dans l'UI).
    # 10.0 → 25.0 = amplitude d'ouverture (25.0 = 01h du lendemain).
    pref_start = fields.Float(
        string="Début préféré (h)", default=10.0,
        help="Heure de début préférée pour ce jour (10 = 10h, 18 = 18h).",
    )
    pref_end = fields.Float(
        string="Fin préférée (h)", default=25.0,
        help="Heure de fin préférée (peut dépasser 24 : 25.0 = 01h le lendemain).",
    )
    hour_preference = fields.Selection(
        [("morning", "Matin (10h-18h)"),
         ("evening", "Soir (18h-01h)"),
         ("flexible", "Flexible")],
        string="Préférence horaire (legacy)",
        default="flexible",
        help="Champ historique conservé pour compatibilité.",
    )
    # Masque demi-heure — source de vérité de la dispo. 30 caractères :
    # chaque caractère = un créneau de 30 min sur l'amplitude 10h→01h.
    # Index 0 = 10:00-10:30, index 1 = 10:30-11:00, …, index 29 = 00:30-01:00.
    # "1" = disponible, "0" = indisponible.
    slot_mask = fields.Char(
        string="Créneaux dispos (30 min)",
        size=30, default="0" * 30,
        help="Masque binaire de 30 caractères représentant la disponibilité "
             "de l'employé par créneaux de 30 minutes sur l'amplitude "
             "d'ouverture (10h → 01h le lendemain).",
    )

    _sql_constraints = [
        ("employee_weekday_unique",
         "unique(employee_id, weekday)",
         "Une seule ligne de disponibilité par employé et par jour."),
    ]

    @api.model
    def _normalize_half_hour(self, value):
        value = float(value or 10.0)
        value = min(25.0, max(10.0, value))
        return round(value * 2.0) / 2.0

    @api.model
    def _mask_from_pref(self, status, pref_start, pref_end):
        """Calcule le slot_mask demi-heure depuis une plage continue
        (status + pref_start + pref_end). Index 0 = 10:00-10:30."""
        if status == "unavailable":
            return "0" * 30
        start_idx = max(0, int(round((pref_start - 10.0) * 2)))
        end_idx = min(30, int(round((pref_end - 10.0) * 2)))
        if end_idx <= start_idx:
            return "0" * 30
        return ("0" * start_idx
                + "1" * (end_idx - start_idx)
                + "0" * (30 - end_idx))

    @api.model
    def _pref_from_mask(self, mask):
        mask = (mask or "").ljust(30, "0")[:30]
        if "1" not in mask:
            return 10.0, 25.0
        start_idx = mask.find("1")
        end_idx = mask.rfind("1") + 1
        return 10.0 + start_idx / 2.0, 10.0 + end_idx / 2.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._refuge_sync_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        vals = dict(vals)
        self._refuge_sync_vals(vals, existing=self[:1] if len(self) == 1 else None)
        return super().write(vals)

    def _refuge_sync_vals(self, vals, existing=None):
        if "slot_mask" in vals:
            mask = (vals.get("slot_mask") or "").ljust(30, "0")[:30]
            vals["slot_mask"] = mask
            pref_start, pref_end = self._pref_from_mask(mask)
            vals.setdefault("pref_start", pref_start)
            vals.setdefault("pref_end", pref_end)
            vals.setdefault("status", "available" if "1" in mask else "unavailable")
        elif {"status", "pref_start", "pref_end"} & set(vals):
            status = vals.get("status", existing.status if existing else "available")
            pref_start = self._normalize_half_hour(
                vals.get("pref_start", existing.pref_start if existing else 10.0)
            )
            pref_end = self._normalize_half_hour(
                vals.get("pref_end", existing.pref_end if existing else 25.0)
            )
            vals["pref_start"] = pref_start
            vals["pref_end"] = pref_end
            vals["slot_mask"] = self._mask_from_pref(status, pref_start, pref_end)

    @api.model
    def _refuge_set_defaults(self, employee_xmlid=None):
        """Applique la spec officielle (idempotent).

        Si `employee_xmlid` est fourni, ne traite que cet employé (utilisé
        par le bouton « Réinitialiser au défaut » du planning). Sinon
        synchronise tous les employés du fichier client.

        Pour chaque employé : statut/préférence selon spec pour les jours
        listés, `unavailable` flexible pour les autres jours (semaine complète).
        """
        targets = (
            {employee_xmlid: _REFUGE_DEFAULT_AVAILABILITY[employee_xmlid]}
            if employee_xmlid and employee_xmlid in _REFUGE_DEFAULT_AVAILABILITY
            else _REFUGE_DEFAULT_AVAILABILITY
        )
        for xmlid, slots in targets.items():
            emp = self.env.ref(xmlid, raise_if_not_found=False)
            if not emp:
                continue
            available_days = {wd: (st, ps, pe) for wd, st, ps, pe in slots}
            for wd in ("0", "1", "2", "3", "4", "5", "6"):
                status, ps, pe = available_days.get(
                    wd, ("unavailable", 10.0, 25.0))
                existing = self.search(
                    [("employee_id", "=", emp.id), ("weekday", "=", wd)],
                    limit=1)
                vals = {"employee_id": emp.id, "weekday": wd,
                        "status": status,
                        "pref_start": ps, "pref_end": pe,
                        "slot_mask": self._mask_from_pref(status, ps, pe)}
                if existing:
                    existing.write(vals)
                else:
                    self.create(vals)
        return True
