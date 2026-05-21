/** @odoo-module */

import { Component } from "@odoo/owl";

const STATUS_CYCLE = ["available", "unavailable"];
const STATUS_LABELS = {
    available: { label: "O", title: "Disponible", cls: "avail-ok" },
    unavailable: { label: "✕", title: "Indisponible", cls: "avail-no" },
};

/* Bornes de la plage horaire — l'amplitude couvre 10h → 01h du lendemain.
   On code 1h en 25 pour rester linéaire (slider/numérique). */
const HOUR_MIN = 10;
const HOUR_MAX = 25;

export class AvailabilityGrid extends Component {
    static template = "refuge_planning.AvailabilityGrid";
    static props = {
        employees: Array,
        availabilities: Array,
        weekdays: Array,
        weekdayLabels: Object,
        ownEmployeeId: { type: [Number, { value: false }], optional: true },
        isAdmin: { type: Boolean, optional: true },
        onChange: Function,
        onChangeRange: Function,
        onResetDefault: Function,
    };

    /* ----------------------- État (lecture des dispos) ------------------- */
    _avail(empId, weekday) {
        return this.props.availabilities.find(
            (x) => x.employee_id === empId && x.weekday === weekday,
        );
    }
    statusFor(empId, weekday) {
        const a = this._avail(empId, weekday);
        return a ? a.status : "unavailable";
    }
    startFor(empId, weekday) {
        const a = this._avail(empId, weekday);
        return a && a.pref_start != null ? a.pref_start : HOUR_MIN;
    }
    endFor(empId, weekday) {
        const a = this._avail(empId, weekday);
        return a && a.pref_end != null ? a.pref_end : HOUR_MAX;
    }

    /* ----------------------- Affichage ----------------------------------- */
    labelFor(status) { return STATUS_LABELS[status] || STATUS_LABELS.unavailable; }

    /** Format "10h" ou "01h" (au-delà de 24, on revient à 0). */
    fmtHour(h) {
        const v = Math.round(h);
        const display = v >= 24 ? v - 24 : v;
        return String(display).padStart(2, "0") + "h";
    }
    rangeLabel(start, end) {
        return `${this.fmtHour(start)}–${this.fmtHour(end)}`;
    }

    /* ----------------------- Permissions --------------------------------- */
    /** Vrai si l'utilisateur connecté peut éditer la ligne de cet employé. */
    canEdit(empId) {
        if (this.props.isAdmin) return true;
        return this.props.ownEmployeeId && empId === this.props.ownEmployeeId;
    }
    rowClass(empId) {
        return this.canEdit(empId) ? "is-editable" : "is-readonly";
    }

    /* ----------------------- Actions ------------------------------------- */
    cycleStatus(empId, weekday) {
        if (!this.canEdit(empId)) return;
        const cur = this.statusFor(empId, weekday);
        const idx = STATUS_CYCLE.indexOf(cur);
        const next = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
        this.props.onChange(
            empId, weekday, next,
            this.startFor(empId, weekday), this.endFor(empId, weekday),
        );
    }

    updateStart(empId, weekday, value) {
        if (!this.canEdit(empId)) return;
        let start = parseInt(value, 10);
        let end = this.endFor(empId, weekday);
        if (start >= end) end = Math.min(HOUR_MAX, start + 1);
        this.props.onChangeRange(empId, weekday, start, end);
    }
    updateEnd(empId, weekday, value) {
        if (!this.canEdit(empId)) return;
        let end = parseInt(value, 10);
        let start = this.startFor(empId, weekday);
        if (end <= start) start = Math.max(HOUR_MIN, end - 1);
        this.props.onChangeRange(empId, weekday, start, end);
    }

    resetEmp(empId) {
        if (!this.canEdit(empId)) return;
        this.props.onResetDefault(empId);
    }

    /* Méthodes triviales exposées au template */
    hourMin() { return HOUR_MIN; }
    hourMax() { return HOUR_MAX; }
}
