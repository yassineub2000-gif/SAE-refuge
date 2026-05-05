/** @odoo-module */

import { Component } from "@odoo/owl";

const STATUS_CYCLE = ["available", "on_request", "unavailable"];
const STATUS_LABELS = {
    available: { label: "O", title: "Disponible", cls: "avail-ok" },
    on_request: { label: "~", title: "Sur demande", cls: "avail-maybe" },
    unavailable: { label: "✕", title: "Indisponible", cls: "avail-no" },
};

export class AvailabilityGrid extends Component {
    static template = "refuge_planning.AvailabilityGrid";
    static props = {
        employees: Array,
        availabilities: Array,
        weekdays: Array,
        weekdayLabels: Object,
        onChange: Function,
        onChangePref: Function,
    };

    statusFor(empId, weekday) {
        const a = this.props.availabilities.find(
            (x) => x.employee_id === empId && x.weekday === weekday,
        );
        return a ? a.status : "unavailable";
    }
    prefFor(empId, weekday) {
        const a = this.props.availabilities.find(
            (x) => x.employee_id === empId && x.weekday === weekday,
        );
        return a ? a.hour_preference : "flexible";
    }

    labelFor(status) { return STATUS_LABELS[status] || STATUS_LABELS.unavailable; }

    cycleStatus(empId, weekday) {
        const cur = this.statusFor(empId, weekday);
        const idx = STATUS_CYCLE.indexOf(cur);
        const next = STATUS_CYCLE[(idx + 1) % STATUS_CYCLE.length];
        this.props.onChange(empId, weekday, next, this.prefFor(empId, weekday));
    }

    employeePref(empId) {
        const first = this.props.availabilities.find((x) => x.employee_id === empId);
        return first ? first.hour_preference : "flexible";
    }

    changePref(empId, ev) {
        this.props.onChangePref(empId, ev.target.value);
    }
}
