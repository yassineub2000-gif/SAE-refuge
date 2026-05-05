/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { refugeRpc } from "@refuge_planning/rpc";
import { AvailabilityGrid } from "@refuge_planning/availability_grid";
import { ShiftTable } from "@refuge_planning/shift_table";

const WEEKDAYS_ORDERED = [1, 2, 3, 4, 5, 6, 0];  // Mar → Dim → Lun
const WEEKDAY_LABELS = {
    0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
    4: "Vendredi", 5: "Samedi", 6: "Dimanche",
};

export class PlanningApp extends Component {
    static template = "refuge_planning.PlanningApp";
    static components = { AvailabilityGrid, ShiftTable };

    setup() {
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
        this.state = useState({
            weekStart: monday.toISOString().slice(0, 10),
            loading: true,
            employees: [],
            availabilities: [],
            shifts: [],
            error: null,
            generating: false,
            uncovered: [],
            manualShift: {
                employee_id: "",
                date: monday.toISOString().slice(0, 10),
                start_time: "10",
                end_time: "18",
                notes: "",
            },
        });
        onWillStart(() => this.fetchState());
    }

    get weekdayOrdered() { return WEEKDAYS_ORDERED; }
    get weekdayLabels() { return WEEKDAY_LABELS; }

    async fetchState() {
        this.state.loading = true;
        try {
            const res = await refugeRpc("/refuge/api/planning/state", {
                week_start: this.state.weekStart,
            });
            this.state.employees = res.employees;
            this.state.availabilities = res.availabilities;
            this.state.shifts = res.shifts;
            this.state.error = null;
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.loading = false;
        }
    }

    async setAvailability(employeeId, weekday, status, pref) {
        await refugeRpc("/refuge/api/planning/set_availability", {
            employee_id: employeeId, weekday, status, hour_preference: pref,
        });
        await this.fetchState();
    }

    async setEmployeePreference(employeeId, pref) {
        await refugeRpc("/refuge/api/planning/set_employee_preference", {
            employee_id: employeeId,
            hour_preference: pref,
        });
        await this.fetchState();
    }

    async generate() {
        this.state.generating = true;
        try {
            const res = await refugeRpc("/refuge/api/planning/generate", {
                week_start: this.state.weekStart,
            });
            this.state.uncovered = res.uncovered || [];
            await this.fetchState();
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.generating = false;
        }
    }

    changeWeek(deltaDays) {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() + deltaDays);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.state.manualShift.date = this.state.weekStart;
        this.fetchState();
    }

    updateManualShift(field, ev) {
        this.state.manualShift[field] = ev.target.value;
    }

    async createManualShift() {
        try {
            await refugeRpc("/refuge/api/planning/create_shift", {
                ...this.state.manualShift,
                employee_id: parseInt(this.state.manualShift.employee_id, 10),
                start_time: parseFloat(this.state.manualShift.start_time),
                end_time: parseFloat(this.state.manualShift.end_time),
            });
            this.state.manualShift.notes = "";
            await this.fetchState();
        } catch (e) {
            this.state.error = e.message;
        }
    }

    async setShiftState(shiftId, state) {
        try {
            await refugeRpc("/refuge/api/planning/set_shift_state", {
                shift_id: shiftId,
                state,
            });
            await this.fetchState();
        } catch (e) {
            this.state.error = e.message;
        }
    }

    async deleteShift(shiftId) {
        try {
            await refugeRpc("/refuge/api/planning/delete_shift", {
                shift_id: shiftId,
            });
            await this.fetchState();
        } catch (e) {
            this.state.error = e.message;
        }
    }
}
