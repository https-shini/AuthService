/* ==========================================================================
   core/session.js — Sessão no navegador
   --------------------------------------------------------------------------
   Guarda SOMENTE o access token (no sessionStorage, como antes: o backend
   entrega o JWT no corpo da resposta e não oferece cookie HttpOnly) e o
   instante do login neste navegador. Senha e e-mail não são gravados.

   As versões anteriores gravavam `auth_pass` (a senha em texto puro) e
   `auth_email`; essas chaves são apagadas assim que este módulo carrega,
   em qualquer página.

   A leitura do payload do JWT aqui serve APENAS para exibir informações
   (expiração, algoritmo) e avisar antes de a sessão expirar. Quem decide
   se o token vale é o servidor: um 401 sempre encerra a sessão local.
   ========================================================================== */

const TOKEN_KEY = "auth_token";
const LOGIN_AT_KEY = "auth_login_at";
const LEGACY_KEYS = ["auth_pass", "auth_email"];

/* sessionStorage com fallback em memória (storage bloqueado). */
const memory = new Map();
const store = {
    get(key) {
        try {
            return window.sessionStorage.getItem(key);
        } catch {
            return memory.get(key) ?? null;
        }
    },
    set(key, value) {
        try {
            window.sessionStorage.setItem(key, value);
        } catch {
            memory.set(key, value);
        }
    },
    remove(key) {
        try {
            window.sessionStorage.removeItem(key);
        } catch {
            /* nada a remover */
        }
        memory.delete(key);
    },
};

export function purgeLegacyData() {
    for (const key of LEGACY_KEYS) {
        store.remove(key);
        try {
            window.localStorage.removeItem(key);
        } catch {
            /* storage bloqueado */
        }
    }
}

purgeLegacyData();

function decodeBase64Url(segment) {
    const base64 = segment.replace(/-/g, "+").replace(/_/g, "/");
    const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
    const binary = window.atob(padded);
    const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
    return new TextDecoder().decode(bytes);
}

/** Decodifica cabeçalho e payload (sem verificar assinatura). */
export function decodeJwt(token) {
    if (typeof token !== "string") return null;
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    try {
        const header = JSON.parse(decodeBase64Url(parts[0]));
        const payload = JSON.parse(decodeBase64Url(parts[1]));
        if (typeof header !== "object" || typeof payload !== "object") return null;
        return { header, payload };
    } catch {
        return null;
    }
}

export function saveSession(token) {
    store.set(TOKEN_KEY, token);
    store.set(LOGIN_AT_KEY, String(Date.now()));
}

export function clearSession() {
    store.remove(TOKEN_KEY);
    store.remove(LOGIN_AT_KEY);
    purgeLegacyData();
}

/**
 * Sessão atual ou null. `malformed` indica um token que nem decodifica —
 * a página deve tratá-lo como inválido sem precisar consultar o servidor.
 */
export function getSession() {
    const token = store.get(TOKEN_KEY);
    if (!token) return null;

    const decoded = decodeJwt(token);
    const exp = decoded?.payload?.exp;
    const loginAt = Number(store.get(LOGIN_AT_KEY));

    return {
        token,
        malformed: decoded === null,
        algorithm:
            typeof decoded?.header?.alg === "string" ? decoded.header.alg : null,
        subject:
            typeof decoded?.payload?.sub === "string" ? decoded.payload.sub : null,
        expiresAt: Number.isFinite(exp) ? new Date(exp * 1000) : null,
        loginAt: Number.isFinite(loginAt) && loginAt > 0 ? new Date(loginAt) : null,
    };
}

export function msUntilExpiry(session, now = Date.now()) {
    return session?.expiresAt ? session.expiresAt.getTime() - now : null;
}

export function isExpired(session, now = Date.now()) {
    const remaining = msUntilExpiry(session, now);
    return remaining !== null && remaining <= 0;
}
