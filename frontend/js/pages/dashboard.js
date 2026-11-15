/* ==========================================================================
   pages/dashboard.js — Painel da conta (home.html)
   --------------------------------------------------------------------------
   Estados: carregando → pronto | sem sessão | sessão expirada/inválida |
   erro de comunicação. Só exibe o que vem de GET /me (id, email) e do
   próprio token (exp, alg). Nunca exibe senha: ela não é guardada.

   Um 401 em /me encerra a sessão local na hora. A expiração lida do token
   também encerra a sessão quando o prazo chega, sem esperar a próxima
   chamada; quem tem a palavra final continua sendo o servidor.
   ========================================================================== */

import { api, ErrorKind } from "../core/api.js";
import { getSession, clearSession, isExpired, msUntilExpiry } from "../core/session.js";
import {
    $,
    setText,
    showAlert,
    clearAlert,
    setBusy,
    copyText,
    formatTime,
    formatDateTime,
    formatDuration,
} from "../core/dom.js";
import { initTheme } from "../core/theme.js";
import { initNav } from "../core/nav.js";

const STATES = ["loading", "empty", "expired", "error", "ready"];
const EXPIRY_WARNING_MS = 5 * 60_000;
const MAX_TIMEOUT_MS = 2 ** 31 - 1;

const alertRegion = $("#dashboard-alert");
const refreshButton = $("#refresh-btn");

let session = getSession();
let expiryTimer = null;
let tickTimer = null;

function showState(name) {
    for (const state of STATES) $(`#state-${state}`).hidden = state !== name;
}

function stopTimers() {
    window.clearTimeout(expiryTimer);
    window.clearInterval(tickTimer);
    expiryTimer = tickTimer = null;
}

/* Encerramento forçado (expirada ou recusada pelo servidor) ---------------- */

function endSession(reason) {
    const expiredAt = session?.expiresAt ?? null;
    clearSession();
    session = null;
    stopTimers();
    hideToken();
    clearAlert(alertRegion);

    if (reason === "expired") {
        setText("expired-title", "Sessão expirada");
        setText(
            "expired-text",
            `${expiredAt ? `Seu token expirou às ${formatTime(expiredAt)}.` : "Seu token expirou."} ` +
                "Por segurança, os dados de autenticação foram removidos deste navegador.",
        );
    } else {
        setText("expired-title", "Sessão inválida");
        setText(
            "expired-text",
            "O servidor não aceitou o token (inválido ou expirado). Por segurança, os dados de " +
                "autenticação foram removidos deste navegador.",
        );
    }
    showState("expired");
    const title = $("#expired-title");
    title.tabIndex = -1;
    title.focus();
}

/* Renderização ------------------------------------------------------------- */

function initialsOf(email) {
    const local = String(email).split("@")[0] ?? "";
    const letters = local.replace(/[^\p{L}\p{N}]/gu, "");
    return (letters.slice(0, 2) || "?").toUpperCase();
}

function renderAccount(account) {
    setText("profile-initials", initialsOf(account.email));
    setText("profile-email", account.email);
    setText("profile-id", `#${account.id}`);
    setText("account-id", account.id);
    setText("account-email", account.email);
    setText("account-fetched", formatTime(new Date()));
}

function renderSession() {
    setText("session-login", session.loginAt ? formatDateTime(session.loginAt) : "não registrado");
    setText("session-alg", session.algorithm ? `${session.algorithm} · JWT` : "não informado");
    setText("session-origin", location.origin);
    setText(
        "session-expires",
        session.expiresAt ? formatDateTime(session.expiresAt) : "não informado pelo token",
    );
    updateRemaining();
}

function updateRemaining() {
    if (!session) return;
    const remaining = msUntilExpiry(session);
    const remainingEl = $("#session-remaining");
    const badge = $("#session-badge");
    const dot = $(".status-dot", badge);

    if (remaining === null) {
        setText(remainingEl, "");
        return;
    }
    if (remaining <= 0) {
        endSession("expired");
        return;
    }

    const soon = remaining <= EXPIRY_WARNING_MS;
    setText(remainingEl, `restam ${formatDuration(remaining)}`);
    remainingEl.dataset.tone = soon ? "warning" : "";
    badge.className = `badge ${soon ? "badge--warning" : "badge--success"}`;
    dot.dataset.state = soon ? "auth" : "ok";
    setText("session-badge-label", soon ? "Expira em breve" : "Sessão ativa");
}

function scheduleExpiry() {
    stopTimers();
    const remaining = msUntilExpiry(session);
    if (remaining === null) return;
    expiryTimer = window.setTimeout(
        () => endSession("expired"),
        Math.min(Math.max(remaining, 0), MAX_TIMEOUT_MS),
    );
    tickTimer = window.setInterval(updateRemaining, 15_000);
}

/* Carregamento ------------------------------------------------------------- */

async function loadAccount({ initial = false } = {}) {
    if (!session) {
        showState("empty");
        return;
    }
    if (session.malformed) {
        endSession("invalid");
        return;
    }
    if (isExpired(session)) {
        endSession("expired");
        return;
    }

    if (initial) showState("loading");
    else setBusy(refreshButton, true, "Atualizando…");

    const result = await api.me(session.token);
    if (!initial) setBusy(refreshButton, false);

    if (result.ok && result.data) {
        renderAccount(result.data);
        renderSession();
        scheduleExpiry();
        showState("ready");
        if (!initial) {
            showAlert(alertRegion, {
                type: "success",
                title: "Dados atualizados",
                message: `GET /me respondeu em ${result.durationMs} ms.`,
            });
        }
        return;
    }

    if (result.error?.kind === ErrorKind.UNAUTHORIZED) {
        endSession("invalid");
        return;
    }

    const detail = `${result.error?.message ?? "Resposta inesperada."} A sessão continua salva neste navegador.`;

    if (initial) {
        setText("error-text", detail);
        showState("error");
    } else {
        showAlert(alertRegion, {
            type: "error",
            title: "Não foi possível atualizar",
            message: detail,
        });
    }
}

/* Token (oculto por padrão) ------------------------------------------------ */

const tokenToggle = $("#token-toggle");
const tokenValue = $("#token-value");
const tokenFeedback = $("#token-feedback");
let feedbackTimer = null;

function hideToken() {
    tokenValue.hidden = true;
    tokenValue.textContent = "";
    tokenToggle.setAttribute("aria-expanded", "false");
    setText($(".btn__label", tokenToggle), "Mostrar token");
}

function showToken() {
    if (!session) return;
    tokenValue.textContent = session.token;
    tokenValue.hidden = false;
    tokenToggle.setAttribute("aria-expanded", "true");
    setText($(".btn__label", tokenToggle), "Ocultar token");
}

function flashFeedback(message, tone = "") {
    tokenFeedback.dataset.tone = tone;
    setText(tokenFeedback, message);
    window.clearTimeout(feedbackTimer);
    feedbackTimer = window.setTimeout(() => setText(tokenFeedback, ""), 3000);
}

tokenToggle.addEventListener("click", () => {
    if (tokenToggle.getAttribute("aria-expanded") === "true") hideToken();
    else showToken();
});

$("#token-copy").addEventListener("click", async () => {
    if (!session) return;
    const copied = await copyText(session.token);
    flashFeedback(
        copied ? "Token copiado." : "Não foi possível copiar. Mostre o token e copie manualmente.",
        copied ? "" : "error",
    );
});

/* Ações -------------------------------------------------------------------- */

refreshButton.addEventListener("click", () => loadAccount());
$("#retry-btn").addEventListener("click", () => loadAccount({ initial: true }));

$("#logout-btn").addEventListener("click", () => {
    stopTimers();
    hideToken();
    clearSession();
    session = null;
    location.assign("index.html?sessao=encerrada");
});

/* Timers podem atrasar em abas em segundo plano: confere ao voltar. */
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && session && isExpired(session)) {
        endSession("expired");
    }
});

/* Inicialização ------------------------------------------------------------ */

initTheme();
initNav();
loadAccount({ initial: true });
