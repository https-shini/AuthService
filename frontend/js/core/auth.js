/* ==========================================================================
   core/auth.js — Chamadas autenticadas, renovação e logout
   --------------------------------------------------------------------------
   `withSession(call)` executa uma chamada com o access token atual e:
     · renova antes, se o token já expirou e há sessão renovável;
     · em 401, renova uma vez e repete a chamada;
     · se a renovação for recusada, limpa a sessão local.

   Renovações são serializadas: uma por vez nesta aba (promessa única) e
   entre abas (Web Locks, quando o navegador tem). Assim duas abas não
   apresentam o mesmo refresh token — o servidor trataria a segunda como
   reuso. Dentro do lock o cookie CSRF é relido, porque outra aba pode ter
   acabado de renovar.
   ========================================================================== */

import { api, ErrorKind } from "./api.js";
import { getSession, saveSession, clearSession, isExpired, getCsrfToken, canRefresh } from "./session.js";

const LOCK_NAME = "authservice-refresh";
let inFlight = null;

async function performRefresh() {
    const csrf = getCsrfToken();
    if (!csrf) return { ok: false, reason: "unavailable" };
    const result = await api.refresh(csrf);
    if (result.ok && typeof result.data?.access_token === "string") {
        saveSession(result.data.access_token, { renewed: true });
        return { ok: true, session: getSession() };
    }
    if (result.status === 0) return { ok: false, reason: "network", error: result.error };
    return { ok: false, reason: "rejected", error: result.error };
}

/** Renova o access token. Resultado: { ok, session? , reason? }. */
export function refreshSession() {
    if (!inFlight) {
        const run = () => performRefresh();
        const locked = navigator.locks?.request
            ? navigator.locks.request(LOCK_NAME, run)
            : run();
        inFlight = locked.finally(() => {
            inFlight = null;
        });
    }
    return inFlight;
}

/**
 * Executa `call(token)` com a sessão atual.
 * Desfechos (outcome):
 *   "ok"        → result é a resposta da chamada (pode ser erro não-401)
 *   "no-session"→ não há token
 *   "expired"   → token vencido e sem renovação possível
 *   "invalid"   → servidor recusou o token (e a renovação)
 *   "network"   → não foi possível renovar por falta de conexão
 * Com `localChecks: false` o token é enviado mesmo malformado, para o
 * servidor dar o veredito (usado pela página de status).
 */
export async function withSession(call, { localChecks = true } = {}) {
    let session = getSession();
    let renewedHere = false;
    if (!session) return { outcome: "no-session" };

    if (localChecks && session.malformed && !canRefresh()) {
        clearSession();
        return { outcome: "invalid" };
    }

    if (session.malformed || isExpired(session)) {
        if (localChecks || canRefresh()) {
            const renewed = await refreshSession();
            if (renewed.ok) {
                session = renewed.session;
                renewedHere = true;
            } else if (renewed.reason === "network") {
                return { outcome: "network", error: renewed.error };
            } else if (localChecks) {
                clearSession();
                return { outcome: session.malformed ? "invalid" : "expired" };
            }
        }
    }

    let result = await call(session.token);
    if (result.error?.kind !== ErrorKind.UNAUTHORIZED) {
        return { outcome: "ok", result, session, renewed: renewedHere };
    }

    const renewed = await refreshSession();
    if (renewed.ok) {
        result = await call(renewed.session.token);
        if (result.error?.kind !== ErrorKind.UNAUTHORIZED) {
            return { outcome: "ok", result, session: renewed.session, renewed: true };
        }
    } else if (renewed.reason === "network") {
        return { outcome: "network", error: renewed.error, result };
    }
    clearSession();
    return { outcome: "invalid", result };
}

/**
 * Encerra a sessão no servidor (revoga access e refresh) e limpa os dados
 * locais. Os dados locais são apagados mesmo se o servidor não responder;
 * `confirmed` diz se o servidor confirmou.
 */
export async function logout() {
    const session = getSession();
    const csrf = getCsrfToken();
    let confirmed = true;
    if (session || csrf) {
        const result = await api.logout(session?.token, csrf);
        confirmed = result.ok;
    }
    clearSession();
    return { confirmed };
}
