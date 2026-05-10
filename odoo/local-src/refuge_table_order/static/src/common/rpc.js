/** @odoo-module */

/**
 * Mini wrapper JSON-RPC autour de fetch.
 *
 * Raison d'être : le cahier des charges (§3.5 "Communication" dans la grille
 * d'évaluation détaillée) interdit les bibliothèques tierces côté OWL. On
 * utilise donc l'API JSON-RPC Odoo via un simple fetch + formatage du corps
 * attendu par le routeur HTTP (type='json').
 *
 *   appel :  await refugeRpc("/refuge/api/table/xxx/menu", {})
 */
export async function refugeRpc(route, params = {}) {
    const response = await fetch(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            params: params,
        }),
    });
    if (!response.ok) {
        throw new Error(`HTTP ${response.status} on ${route}`);
    }
    const payload = await response.json();
    if (payload.error) {
        // Erreur côté serveur Odoo (traceback, permission, etc.)
        throw new Error(payload.error.data?.message || payload.error.message || "RPC error");
    }
    const result = payload.result || {};
    if (result.error) {
        // Erreur métier renvoyée volontairement par notre controller
        throw new Error(result.error);
    }
    return result;
}
