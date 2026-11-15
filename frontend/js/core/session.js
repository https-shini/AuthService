/* ==========================================================================
   core/session.js — Sessão no navegador
   --------------------------------------------------------------------------
   Guarda SOMENTE o access token (no sessionStorage: o backend entrega o
   JWT de acesso no corpo da resposta, para manter o fluxo Bearer) e o
   instante do login neste navegador. Senha e e-mail não são gravados.

   O refresh token fica num cookie HttpOnly que este código não consegue
   ler. O que dá para ler é o cookie CSRF que o acompanha: a presença dele
   indica que há uma sessão renovável, e o valor vai no header
   X-CSRF-Token de /refresh e /logout.

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

export function saveSession(token, { renewed = false } = {}) {
    store.set(TOKEN_KEY, token);
    // Renovação mantém o horário do login original.
    if (!renewed || !store.get(LOGIN_AT_KEY)) store.set(LOGIN_AT_KEY, String(Date.now()));
}

/* Nome com prefixo __Host- em HTTPS/localhost (COOKIE_SECURE) e sem ele
   quando o servidor roda com cookies não-Secure. */
const CSRF_COOKIE_NAMES = ["__Host-auth_csrf", "auth_csrf"];

export function getCsrfToken() {
    const cookies = Object.fromEntries(
        document.cookie
            .split(";")
            .map((part) => part.trim())
            .filter(Boolean)
            .map((part) => {
                const index = part.indexOf("=");
                return [part.slice(0, index), decodeURIComponent(part.slice(index + 1))];
            }),
    );
    for (const name of CSRF_COOKIE_NAMES) {
        if (cookies[name]) return cookies[name];
    }
    return null;
}

/** Há uma sessão renovável no servidor (cookie CSRF presente)? */
export const canRefresh = () => getCsrfToken() !== null;

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
