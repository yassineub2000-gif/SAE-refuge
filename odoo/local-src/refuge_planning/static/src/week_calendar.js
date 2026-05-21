/** @odoo-module */

import { Component } from "@odoo/owl";
import { colorFor } from "@refuge_planning/summary_cards";

const OPEN_FROM = 10;
const OPEN_TO = 25;          // 25 = 01h le lendemain
const DAY_INDICES = [1, 2, 3, 4, 5, 6];   // Mar à Dim (weekday Python)
const SLOT_COUNT = 30;
const DAY_LABELS = {
    1: "Mardi", 2: "Mercredi", 3: "Jeudi",
    4: "Vendredi", 5: "Samedi", 6: "Dimanche",
};

/** Vue calendrier hebdomadaire : jours en colonnes, heures en lignes, shifts
 *  affichés comme blocs colorés positionnés en CSS grid. */
export class WeekCalendar extends Component {
    static template = "refuge_planning.WeekCalendar";
    static props = {
        employees: Array,
        shifts: Array,
        weekStart: String,           // ISO "YYYY-MM-DD" du lundi
        canManage: Boolean,          // admin → peut valider/supprimer
        ownEmployeeId: { type: [Number, { value: false }], optional: true },
        onValidateShift: Function,
        onCancelShift: Function,
        onDeleteShift: Function,
        onEditShift: Function,
    };

    get dayIndices() { return DAY_INDICES; }
    get hourLabels() {
        const labels = [];
        for (let slot = 0; slot < SLOT_COUNT; slot++) {
            const absoluteHour = OPEN_FROM + slot / 2;
            const displayHour = Math.floor(absoluteHour >= 24 ? absoluteHour - 24 : absoluteHour);
            const minutes = slot % 2 === 0 ? "00" : "30";
            labels.push(`${String(displayHour).padStart(2, "0")}h${minutes}`);
        }
        return labels;
    }
    get hourRange() {
        return Array.from({ length: SLOT_COUNT }, (_, i) => i);
    }

    /** Date ISO du jour de la semaine (weekday 1..6). monday = lundi. */
    dateFor(weekdayPython) {
        const monday = new Date(this.props.weekStart + "T00:00:00");
        const d = new Date(monday);
        d.setDate(monday.getDate() + weekdayPython);
        return d.toISOString().slice(0, 10);
    }

    weekdayPyFromIso(iso) {
        // Python weekday : Lun=0, Dim=6. JS getDay : Dim=0, Lun=1.
        const d = new Date(iso + "T00:00:00");
        const js = d.getDay();
        return (js + 6) % 7;
    }

    /** Shifts d'un jour donné, triés par heure de début. */
    shiftsOfDay(weekdayPy) {
        return this.props.shifts
            .filter((s) => this.weekdayPyFromIso(s.date) === weekdayPy)
            .sort((a, b) => a.start_time - b.start_time);
    }

    /** Style CSS grid : positionne le shift sur les bonnes lignes. */
    shiftStyle(shift, idx) {
        const start = shift.start_time;
        // end < start → traversée de minuit (ex. 18→1 = 18→25)
        const rawEnd = shift.end_time < shift.start_time
            ? shift.end_time + 24
            : shift.end_time;
        const startRow = Math.round((start - OPEN_FROM) * 2) + 2;
        const endRow = Math.round((rawEnd - OPEN_FROM) * 2) + 2;
        const col = idx.col + 2;   // +1 col d'heures + 1-indexed
        const c = colorFor(idx.empIdx);
        return [
            `grid-row: ${startRow} / ${endRow};`,
            `grid-column: ${col};`,
            `background: ${c.bg};`,
            `border-left: 4px solid ${c.border};`,
            `color: ${c.fg};`,
        ].join(" ");
    }

    /** Index d'un employé dans la liste triée → pour la couleur. */
    empColorIndex(empId) {
        const sorted = [...this.props.employees].sort((a, b) => a.id - b.id);
        const i = sorted.findIndex((e) => e.id === empId);
        return i < 0 ? 0 : i;
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

    durationFor(shift) {
        const rawEnd = shift.end_time < shift.start_time
            ? shift.end_time + 24
            : shift.end_time;
        return rawEnd - shift.start_time;
    }

    canEditShift(shift) {
        if (this.props.canManage) return true;
        return this.props.ownEmployeeId && shift.employee_id === this.props.ownEmployeeId;
    }

    /* --- Couverture par jour (% du créneau 10h-01h couvert par au moins 1
          barman) — utile dans le bandeau coverage en bas. */
    coverageFor(weekdayPy) {
        const dayShifts = this.shiftsOfDay(weekdayPy);
        const covered = new Set();
        for (const s of dayShifts.filter((shift) => shift.state !== "cancelled")) {
            const rawEnd = s.end_time < s.start_time ? s.end_time + 24 : s.end_time;
            const startSlot = Math.round((s.start_time - OPEN_FROM) * 2);
            const endSlot = Math.round((rawEnd - OPEN_FROM) * 2);
            for (let slot = startSlot; slot < endSlot; slot++) {
                covered.add(slot);
            }
        }
        const total = SLOT_COUNT;
        return Math.round((covered.size / total) * 100);
    }

    dayLabel(weekdayPy) { return DAY_LABELS[weekdayPy]; }
}
