/** @odoo-module */

/* Gestion du thème clair/sombre, partagée par toutes les apps OWL.
   Clair par défaut ; suit l'OS au 1er chargement ; choix mémorisé par
   appareil (localStorage). Le <head> de chaque page applique déjà le thème
   avant le rendu (anti-flash) ; ici on expose le toggle runtime. */

const KEY = "refuge-theme";

export function currentTheme() {
    return document.documentElement.getAttribute("data-theme") || "light";
}

export function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    try {
        localStorage.setItem(KEY, theme);
    } catch (e) {
        /* stockage indisponible (navigation privée) — non bloquant */
    }
}

export function toggleTheme() {
    applyTheme(currentTheme() === "dark" ? "light" : "dark");
    return currentTheme();
}

export function initTheme() {
    let theme = null;
    try {
        theme = localStorage.getItem(KEY);
    } catch (e) {
        /* ignore */
    }
    if (!theme) {
        theme =
            window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: dark)").matches
                ? "dark"
                : "light";
    }
    document.documentElement.setAttribute("data-theme", theme);
    return theme;
}
