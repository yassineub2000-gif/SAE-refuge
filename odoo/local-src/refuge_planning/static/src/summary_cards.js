/** @odoo-module */

import { Component } from "@odoo/owl";

/* Palette d'identification employé — 4 couleurs distinctes coordonnées avec
   le design system (terracotta, bleu, vert, or). Index = position dans la
   liste triée par id (stable d'une semaine à l'autre). */
const EMP_COLORS = [
    { bg: "#E8F0FE", border: "#2563EB", fg: "#1B4FCC", emoji: "🔵" },  // bleu
    { bg: "#F6E7DC", border: "#C0532B", fg: "#A8431F", emoji: "🟠" },  // terracotta
    { bg: "#DDF0E7", border: "#2E7D5B", fg: "#1F5C42", emoji: "🟢" },  // vert
    { bg: "#F8E9C7", border: "#B5790F", fg: "#7A5108", emoji: "🟡" },  // or
];

export function colorFor(empIndex) {
    return EMP_COLORS[empIndex % EMP_COLORS.length];
}

/** Bandeau supérieur : une carte par employé avec heures planifiées / cible,
 *  barre de progression, alertes (dépassement / sous-cible). */
export class SummaryCards extends Component {
    static template = "refuge_planning.SummaryCards";
    static props = {
        employees: Array,
        shifts: Array,
    };

    plannedHours(empId) {
        return this.props.shifts
            .filter((s) => s.employee_id === empId && s.state !== "cancelled")
            .reduce((tot, s) => tot + (s.duration || 0), 0);
    }

    targetFor(emp) {
        return emp.weekly_hours || 24;
    }

    progressPct(emp) {
        const planned = this.plannedHours(emp.id);
        const target = this.targetFor(emp);
        return Math.min(100, Math.round((planned / target) * 100));
    }

    alertFor(emp) {
        const planned = this.plannedHours(emp.id);
        const target = this.targetFor(emp);
        if (planned > target + 0.01) return { kind: "over", label: "Dépasse" };
        if (planned < target - 2) return { kind: "under", label: "Sous-cible" };
        return null;
    }

    colorFor(idx) { return colorFor(idx); }
    fmtHours(h) { return (Math.round(h * 10) / 10) + "h"; }
}
