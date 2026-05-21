/** @odoo-module */

import { Component } from "@odoo/owl";
import { colorFor } from "@refuge_planning/summary_cards";

const DAY_LABELS_FULL = {
    0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
    4: "Vendredi", 5: "Samedi", 6: "Dimanche",
};

/** Vue centrée sur l'employé connecté : ses shifts de la semaine + résumé
 *  de ses disponibilités. Gérant (sans employé lié) → message dédié. */
export class MySpace extends Component {
    static template = "refuge_planning.MySpace";
    static props = {
        employees: Array,
        shifts: Array,
        availabilities: Array,
        weekStart: String,
        ownEmployeeId: { type: [Number, { value: false }], optional: true },
        isAdmin: Boolean,
        onGoToAvailabilities: Function,
    };

    /** Employé connecté (ou null si gérant). */
    get me() {
        if (!this.props.ownEmployeeId) return null;
        return this.props.employees.find(
            (e) => e.id === this.props.ownEmployeeId) || null;
    }

    get myShifts() {
        if (!this.me) return [];
        return this.props.shifts
            .filter((s) => s.employee_id === this.me.id)
            .sort((a, b) => (a.date + a.start_time) > (b.date + b.start_time) ? 1 : -1);
    }

    get myAvailabilities() {
        if (!this.me) return [];
        return this.props.availabilities
            .filter((a) => a.employee_id === this.me.id)
            .sort((a, b) => a.weekday - b.weekday);
    }

    get myTotalHours() {
        return this.myShifts
            .filter((shift) => shift.state !== "cancelled")
            .reduce((t, s) => t + (s.duration || 0), 0);
    }

    get myTarget() {
        return this.me ? (this.me.weekly_hours || 24) : 0;
    }

    myColor() {
        if (!this.me) return null;
        const sorted = [...this.props.employees].sort((a, b) => a.id - b.id);
        const i = sorted.findIndex((e) => e.id === this.me.id);
        return colorFor(i < 0 ? 0 : i);
    }

    fmtTime(h) {
        const v = Math.round(h);
        const disp = v >= 24 ? v - 24 : v;
        return `${String(disp).padStart(2, "0")}h`;
    }

    fmtRange(start, end) {
        const rawEnd = end < start ? end + 24 : end;
        return `${this.fmtTime(start)}–${this.fmtTime(rawEnd)}`;
    }

    durationFor(s) {
        const rawEnd = s.end_time < s.start_time ? s.end_time + 24 : s.end_time;
        return rawEnd - s.start_time;
    }

    dateLabel(iso) {
        const d = new Date(iso + "T00:00:00");
        const wd = DAY_LABELS_FULL[(d.getDay() + 6) % 7];
        return `${wd} ${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
    }

    weekdayLabel(wd) { return DAY_LABELS_FULL[wd]; }

    availTextFor(a) {
        if (a.status === "unavailable") return "Indisponible";
        const s = a.pref_start != null ? a.pref_start : 10;
        const e = a.pref_end != null ? a.pref_end : 25;
        return `${this.fmtTime(s)}–${this.fmtTime(e)}`;
    }

    availClass(a) {
        if (a.status === "unavailable") return "is-no";
        return "is-ok";
    }
}
