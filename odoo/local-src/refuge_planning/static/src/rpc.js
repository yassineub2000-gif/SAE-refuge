/** @odoo-module */

/** Wrapper JSON-RPC minimal — identique (duplication volontaire) à celui de
 *  refuge_table_order pour garder les deux modules OWL indépendants et éviter
 *  une dépendance JS entre eux. */
export async function refugeRpc(route, params = {}) {
    const response = await fetch(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
    });
    if (!response.ok) throw new Error(`HTTP ${response.status} on ${route}`);
    const payload = await response.json();
    if (payload.error) {
        throw new Error(payload.error.data?.message || payload.error.message || "RPC error");
    }
    const result = payload.result || {};
    if (result.error) throw new Error(result.error);
    return result;
}
