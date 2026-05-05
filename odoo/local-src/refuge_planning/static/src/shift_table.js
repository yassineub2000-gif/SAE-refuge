/** @odoo-module */

import { Component } from "@odoo/owl";

export class ShiftTable extends Component {
    static template = "refuge_planning.ShiftTable";
    static props = {
        shifts: Array,
        employees: Array,
        weekStart: String,
        onSetState: Function,
        onDelete: Function,
    };

    get weekDays() {
        const out = [];
        const start = new Date(this.props.weekStart);
        for (let i = 0; i < 7; i++) {
            const d = new Date(start);
            d.setDate(start.getDate() + i);
            out.push({
                iso: d.toISOString().slice(0, 10),
                label: d.toLocaleDateString("fr-FR", { weekday: "short", day: "2-digit", month: "2-digit" }),
            });
        }
        return out;
    }

    shiftsFor(dateIso) {
        return this.props.shifts.filter((s) => s.date === dateIso)
            .sort((a, b) => a.start_time - b.start_time);
    }

    formatHour(h) {
        const hh = Math.floor(h);
        const mm = Math.round((h - hh) * 60);
        return `${String(hh).padStart(2, "0")}h${String(mm).padStart(2, "0")}`;
    }

    totalHoursPerEmployee() {
        const totals = {};
        for (const s of this.props.shifts) {
            totals[s.employee_id] = (totals[s.employee_id] || 0) + s.duration;
        }
        return totals;
    }

    stateLabel(state) {
        return {
            draft: "Proposé",
            confirmed: "Validé",
            cancelled: "Annulé",
        }[state] || state;
    }
}
