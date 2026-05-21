/** @odoo-module */

import { Component, useState, onWillStart } from "@odoo/owl";
import { refugeRpc } from "@refuge_planning/rpc";
import { AvailabilityHeatmap } from "@refuge_planning/availability_heatmap";
import { SummaryCards } from "@refuge_planning/summary_cards";
import { WeekCalendar } from "@refuge_planning/week_calendar";
import { MySpace } from "@refuge_planning/my_space";
import { ShiftTable } from "@refuge_planning/shift_table";
import { AppHeader } from "@refuge_aventuriers/theme/app_header";

const WEEKDAYS_ORDERED = [1, 2, 3, 4, 5, 6, 0];  // Mar → Dim → Lun
const WEEKDAY_LABELS = {
    0: "Lundi", 1: "Mardi", 2: "Mercredi", 3: "Jeudi",
    4: "Vendredi", 5: "Samedi", 6: "Dimanche",
};
const SHIFT_STATES = ["draft", "confirmed", "cancelled"];
const EMPTY_EDITOR = () => ({
    id: false,
    employee_id: false,
    date: "",
    start_time: 10,
    end_time: 18,
    state: "draft",
    notes: "",
});

export class PlanningApp extends Component {
    static template = "refuge_planning.PlanningApp";
    static components = {
        AppHeader, AvailabilityHeatmap, SummaryCards, WeekCalendar, MySpace, ShiftTable,
    };

    setup() {
        const today = new Date();
        const monday = new Date(today);
        monday.setDate(today.getDate() - ((today.getDay() + 6) % 7));
        this.state = useState({
            tab: "planning",   // "planning" | "avail" | "me"
            weekStart: monday.toISOString().slice(0, 10),
            loading: true,
            employees: [],
            availabilities: [],
            shifts: [],
            error: null,
            generating: false,
            validating: false,
            savingShift: false,
            lastReport: null,  // {created, uncovered}
            ownEmployeeId: false,
            isAdmin: false,
            shiftEditor: EMPTY_EDITOR(),
        });
        onWillStart(() => this.fetchState());
    }

    get weekdayOrdered() { return WEEKDAYS_ORDERED; }
    get weekdayLabels() { return WEEKDAY_LABELS; }

    /** Au premier chargement, un employé non-admin tombe sur "Mon espace"
     *  (focus immédiat sur ses propres shifts). Le gérant reste sur le
     *  calendrier global. */
    _pickDefaultTab() {
        if (!this.state.isAdmin && this.state.ownEmployeeId) {
            this.state.tab = "me";
        }
    }

    get draftCount() {
        return this.state.shifts.filter((s) => s.state === "draft").length;
    }

    get orderedEmployees() {
        return [...this.state.employees].sort((a, b) => a.name.localeCompare(b.name));
    }

    get shiftStateOptions() {
        return SHIFT_STATES;
    }

    get selectedShiftEmployee() {
        return this.state.employees.find((emp) => emp.id === this.state.shiftEditor.employee_id);
    }

    /* ------------------------------------------------------- data */

    async fetchState() {
        this.state.loading = true;
        try {
            const res = await refugeRpc("/refuge/api/planning/state", {
                week_start: this.state.weekStart,
            });
            this.state.employees = res.employees;
            this.state.availabilities = res.availabilities;
            this.state.shifts = res.shifts;
            this.state.ownEmployeeId = res.own_employee_id || false;
            this.state.isAdmin = !!res.is_admin;
            this.state.error = null;
            if (this.state.loading) {
                // tout premier chargement : choisir le bon onglet par défaut
                this._pickDefaultTab();
            }
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.loading = false;
        }
    }

    changeWeek(deltaDays) {
        const d = new Date(this.state.weekStart);
        d.setDate(d.getDate() + deltaDays);
        this.state.weekStart = d.toISOString().slice(0, 10);
        this.state.lastReport = null;
        this.fetchState();
    }

    setTab(tab) {
        this.state.tab = tab;
    }

    /* ---------------------------------------------- shifts (manager) */

    async generate() {
        if (this.draftCount && !window.confirm(
            "Une génération précédente existe (brouillons). Continuer écrasera ces brouillons.")) {
            return;
        }
        this.state.generating = true;
        try {
            const res = await refugeRpc("/refuge/api/planning/generate", {
                week_start: this.state.weekStart,
            });
            this.state.lastReport = {
                created: res.created || 0,
                uncovered: res.uncovered || [],
            };
            await this.fetchState();
        } catch (e) {
            this.state.error =
                e.message === "not_allowed"
                    ? "Seul le gérant peut générer le planning."
                    : e.message;
        } finally {
            this.state.generating = false;
        }
    }

    async validateWeek() {
        if (!this.draftCount) return;
        if (!window.confirm(
            `Valider ${this.draftCount} shift(s) en brouillon pour cette semaine ?`)) {
            return;
        }
        this.state.validating = true;
        try {
            const res = await refugeRpc("/refuge/api/planning/validate_week", {
                week_start: this.state.weekStart,
            });
            this.state.lastReport = {
                validated: res.validated,
                uncovered: this.state.lastReport ? this.state.lastReport.uncovered : [],
            };
            await this.fetchState();
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.validating = false;
        }
    }

    async validateShift(shiftId) {
        await this._setShiftState(shiftId, "confirmed");
    }

    async cancelShift(shiftId) {
        await this._setShiftState(shiftId, "cancelled");
    }

    async _setShiftState(shiftId, state) {
        try {
            await refugeRpc("/refuge/api/planning/set_shift_state", {
                shift_id: shiftId, state,
            });
            await this.fetchState();
        } catch (e) {
            this.state.error =
                e.message === "not_allowed"
                    ? "Vous ne pouvez pas modifier le shift d'un autre employé."
                    : e.message;
        }
    }

    async deleteShift(shiftId) {
        if (!window.confirm("Supprimer ce shift ?")) return;
        try {
            await refugeRpc("/refuge/api/planning/delete_shift", {
                shift_id: shiftId,
            });
            await this.fetchState();
        } catch (e) {
            this.state.error =
                e.message === "not_allowed"
                    ? "Vous ne pouvez pas supprimer le shift d'un autre employé."
                    : e.message;
        }
    }

    openNewShift() {
        const monday = new Date(this.state.weekStart + "T00:00:00");
        monday.setDate(monday.getDate() + 1);
        this.state.shiftEditor = {
            ...EMPTY_EDITOR(),
            employee_id: this.state.employees[0] ? this.state.employees[0].id : false,
            date: monday.toISOString().slice(0, 10),
        };
    }

    editShift(shiftId) {
        const shift = this.state.shifts.find((item) => item.id === shiftId);
        if (!shift) {
            return;
        }
        const normalizedEnd = shift.end_time < shift.start_time ? shift.end_time + 24 : shift.end_time;
        this.state.shiftEditor = {
            id: shift.id,
            employee_id: shift.employee_id,
            date: shift.date,
            start_time: shift.start_time,
            end_time: normalizedEnd,
            state: shift.state,
            notes: shift.notes || "",
        };
    }

    cancelShiftEditor() {
        this.state.shiftEditor = EMPTY_EDITOR();
    }

    updateShiftEditor(field, value) {
        this.state.shiftEditor[field] = value;
    }

    async saveShift() {
        const payload = {
            employee_id: parseInt(this.state.shiftEditor.employee_id, 10),
            date: this.state.shiftEditor.date,
            start_time: parseFloat(this.state.shiftEditor.start_time),
            end_time: parseFloat(this.state.shiftEditor.end_time) >= 24
                ? parseFloat(this.state.shiftEditor.end_time) - 24
                : parseFloat(this.state.shiftEditor.end_time),
            state: this.state.shiftEditor.state,
            notes: this.state.shiftEditor.notes || "",
        };
        this.state.savingShift = true;
        try {
            if (this.state.shiftEditor.id) {
                await refugeRpc("/refuge/api/planning/update_shift", {
                    shift_id: this.state.shiftEditor.id,
                    ...payload,
                });
            } else {
                await refugeRpc("/refuge/api/planning/create_shift", payload);
            }
            this.cancelShiftEditor();
            await this.fetchState();
        } catch (e) {
            this.state.error = e.message;
        } finally {
            this.state.savingShift = false;
        }
    }

    /* -------------------------------------------------------- helpers */

    fmtWeek() {
        const d = new Date(this.state.weekStart + "T00:00:00");
        const end = new Date(d); end.setDate(d.getDate() + 6);
        const f = (x) => `${String(x.getDate()).padStart(2, "0")}/${String(x.getMonth() + 1).padStart(2, "0")}`;
        return `Semaine du ${f(d)} au ${f(end)}`;
    }

    fmtEditorHour(value) {
        const numeric = parseFloat(value);
        const display = numeric >= 24 ? numeric - 24 : numeric;
        const hours = Math.floor(display);
        const minutes = Math.round((display - hours) * 60);
        return `${String(hours).padStart(2, "0")}h${String(minutes).padStart(2, "0")}`;
    }

    formOptions() {
        const values = [];
        for (let slot = 0; slot <= 30; slot++) {
            const value = 10 + slot / 2;
            if (value > 25) continue;
            values.push({ value, label: this.fmtEditorHour(value) });
        }
        return values;
    }
}
