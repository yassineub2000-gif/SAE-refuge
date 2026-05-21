/** @odoo-module */

import { Component } from "@odoo/owl";

/* 30 slots de 30 min, jours Mar→Dim (weekday 1..6) en colonnes. */
const SLOTS = 30;
const DAYS = [1, 2, 3, 4, 5, 6];
const DAY_LABELS = {
    1: "Mar", 2: "Mer", 3: "Jeu", 4: "Ven", 5: "Sam", 6: "Dim",
};
const STATUS_META = {
    available: { label: "Disponible", short: "O", cls: "is-available" },
    unavailable: { label: "Indisponible", short: "✕", cls: "is-unavailable" },
};

/** Étiquette d'un slot : 10:00, 10:30, …, 00:30 */
function slotLabel(slot) {
    const h = Math.floor(10 + slot / 2);
    const m = (slot % 2) * 30;
    const dispH = h >= 24 ? h - 24 : h;
    return `${String(dispH).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

export class AvailabilityHeatmap extends Component {
    static template = "refuge_planning.AvailabilityHeatmap";
    static props = {
        employees: Array,
        availabilities: Array,
        ownEmployeeId: { type: [Number, { value: false }], optional: true },
        isAdmin: { type: Boolean, optional: true },
        onSetMask: { type: Function, optional: true },
    };

    /* --- Lecture du mask courant --- */
    maskFor(empId, weekday) {
        const a = this.props.availabilities.find(
            (x) => x.employee_id === empId && x.weekday === weekday,
        );
        return (a && a.slot_mask) ? a.slot_mask : "0".repeat(SLOTS);
    }
    isOn(empId, weekday, slot) {
        return this.maskFor(empId, weekday).charAt(slot) === "1";
    }
    statusFor(empId, weekday) {
        const a = this.props.availabilities.find(
            (x) => x.employee_id === empId && x.weekday === weekday,
        );
        const mask = this.maskFor(empId, weekday);
        if (!mask.includes("1")) return "unavailable";
        return "available";
    }
    statusMeta(empId, weekday) {
        return STATUS_META[this.statusFor(empId, weekday)] || STATUS_META.unavailable;
    }
    lockReason(empId) {
        if (this.canEdit(empId)) return "";
        return "Lecture seule — vous ne pouvez éditer que votre propre ligne.";
    }

    /* --- Permissions --- */
    /** Le gérant édite tout le monde ; un employé seulement sa propre ligne. */
    canEdit(empId) {
        if (this.props.isAdmin) return true;
        return !!this.props.ownEmployeeId && empId === this.props.ownEmployeeId;
    }

    /* --- Édition --- */
    _emit(empId, weekday, mask) {
        if (this.props.onSetMask) {
            this.props.onSetMask(empId, weekday, mask);
        }
    }
    /** Bascule la journée entière : si dispo → tout couper, sinon tout ouvrir. */
    toggleDay(empId, weekday) {
        if (!this.canEdit(empId)) return;
        const on = this.maskFor(empId, weekday).includes("1");
        this._emit(empId, weekday, (on ? "0" : "1").repeat(SLOTS));
    }
    /** Active / désactive un créneau de 30 min. */
    toggleSlot(empId, weekday, slot) {
        if (!this.canEdit(empId)) return;
        const mask = this.maskFor(empId, weekday).padEnd(SLOTS, "0").split("");
        mask[slot] = mask[slot] === "1" ? "0" : "1";
        this._emit(empId, weekday, mask.join(""));
    }

    /* --- Affichage --- */
    get slotsList() {
        return Array.from({ length: SLOTS }, (_, i) => i);
    }
    get days() { return DAYS; }
    dayLabel(d) { return DAY_LABELS[d]; }
    /** N'affiche un label heure qu'aux slots de début d'heure (slot pair). */
    slotLabel(slot) {
        if (slot % 2 !== 0) return "";
        return slotLabel(slot);
    }
    slotTitle(empId, weekday, slot) {
        return `${slotLabel(slot)} → ${slotLabel(slot + 1)}`;
    }

    /** Empêcher la sélection de texte pendant un drag. */
    onMouseMoveGrid() {}
}
