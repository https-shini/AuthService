/* ==========================================================================
   pages/dashboard.js — Painel da conta (home.html)
   --------------------------------------------------------------------------
   Estados: carregando → pronto | sem sessão | sessão expirada/inválida |
   erro de comunicação. Só exibe o que vem de GET /me (id, email, name) e
   do próprio token (exp, alg). Nunca exibe senha: ela não é guardada.

   O access token é curto. Quando vence, o painel pede um novo em
   POST /refresh (cookie HttpOnly + CSRF); sem renovação possível, a sessão
   local é encerrada. "Encerrar sessão" revoga a sessão no servidor.
   ========================================================================== */

import { api } from "../core/api.js";
import { withSession, refreshSession, logout } from "../core/auth.js";
import { getSession, clearSession, msUntilExpiry, canRefresh } from "../core/session.js";
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
            `${expiredAt ? `O token de acesso expirou às ${formatTime(expiredAt)} e não pôde ser renovado.` : "A sessão expirou."} ` +
                "Por segurança, os dados de autenticação foram removidos deste navegador.",
        );
    } else {
        setText("expired-title", "Sessão inválida");
        setText(
            "expired-text",
            "O servidor não aceitou o token (inválido, expirado ou revogado). Por segurança, os dados de " +
                "autenticação foram removidos deste navegador.",
        );
    }
    showState("expired");
    const title = $("#expired-title");
    title.tabIndex = -1;
    title.focus();
}

/* Renderização ------------------------------------------------------------- */

function initialsOf(account) {
    const source = account.name || String(account.email).split("@")[0] || "";
    const words = source.split(/\s+/).filter(Boolean);
    const letters =
        words.length > 1
            ? words[0][0] + words[words.length - 1][0]
            : source.replace(/[^\p{L}\p{N}]/gu, "").slice(0, 2);
    return (letters || "?").toUpperCase();
}

function renderAccount(account) {
    setText("profile-initials", initialsOf(account));
    setText("profile-title", account.name || account.email);
    const emailLine = $("#profile-email");
    emailLine.hidden = !account.name;
    setText(emailLine, account.name ? account.email : "");
    setText("profile-id", `Conta #${account.id}`);
    setText("account-id", account.id);
    setText("account-name", account.name || "não informado");
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
    setText(
        "session-renewal",
        canRefresh() ? "automática · até fechar o navegador" : "indisponível · entre de novo ao expirar",
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
        renewOnExpiry();
        return;
    }

    // Com renovação disponível, o fim do token não é o fim da sessão.
    const renewable = canRefresh();
    const soon = !renewable && remaining <= EXPIRY_WARNING_MS;
    setText(remainingEl, renewable ? `renova em ${formatDuration(remaining)}` : `restam ${formatDuration(remaining)}`);
    remainingEl.dataset.tone = soon ? "warning" : "";
    badge.className = `badge ${soon ? "badge--warning" : "badge--success"}`;
    dot.dataset.state = soon ? "auth" : "ok";
    setText("session-badge-label", soon ? "Expira em breve" : "Sessão ativa");
}

function scheduleExpiry() {
    stopTimers();
    const remaining = msUntilExpiry(session);
    if (remaining === null) return;
    expiryTimer = window.setTimeout(renewOnExpiry, Math.min(Math.max(remaining, 0), MAX_TIMEOUT_MS));
    tickTimer = window.setInterval(updateRemaining, 15_000);
}

let renewing = false;

async function renewOnExpiry() {
    if (renewing || !session) return;
    renewing = true;
    stopTimers();
    const renewed = canRefresh() ? await refreshSession() : { ok: false, reason: "unavailable" };
    renewing = false;

    if (renewed.ok) {
        session = renewed.session;
        renderSession();
        scheduleExpiry();
        showAlert(alertRegion, {
            type: "info",
            title: "Sessão renovada",
            message: `Novo token de acesso emitido às ${formatTime(new Date())}.`,
        });
        return;
    }
    if (renewed.reason === "network") {
        showAlert(alertRegion, {
            type: "error",
            title: "Não foi possível renovar a sessão",
            message: "Sem comunicação com o servidor. Use \"Atualizar dados\" quando a conexão voltar.",
        });
        return;
    }
    endSession("expired");
}

/* Carregamento ------------------------------------------------------------- */

async function loadAccount({ initial = false } = {}) {
    if (!getSession()) {
        stopTimers();
        showState("empty");
        return;
    }

    if (initial) showState("loading");
    else setBusy(refreshButton, true, "Atualizando…");

    const { outcome, result, error } = await withSession((token) => api.me(token));
    if (!initial) setBusy(refreshButton, false);

    if (outcome === "expired" || outcome === "invalid") {
        endSession(outcome);
        return;
    }
    if (outcome === "no-session") {
        showState("empty");
        return;
    }

    if (outcome === "ok" && result.ok && result.data) {
        session = getSession();
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

    const failure = result?.error ?? error ?? { message: "Resposta inesperada." };
    const detail = `${failure.message} A sessão continua salva neste navegador.`;
    if (initial || $("#state-ready").hidden) {
        setText("error-text", detail);
        showState("error");
    } else {
        showAlert(alertRegion, { type: "error", title: "Não foi possível atualizar", message: detail });
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
    const current = getSession();
    if (!current) return;
    tokenValue.textContent = current.token;
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
    const current = getSession();
    if (!current) return;
    const copied = await copyText(current.token);
    flashFeedback(
        copied ? "Token copiado." : "Não foi possível copiar. Mostre o token e copie manualmente.",
        copied ? "" : "error",
    );
});

/* Ações -------------------------------------------------------------------- */

refreshButton.addEventListener("click", () => loadAccount());
$("#retry-btn").addEventListener("click", () => loadAccount({ initial: true }));

const logoutButton = $("#logout-btn");
logoutButton.addEventListener("click", async () => {
    if (logoutButton.disabled) return;
    setBusy(logoutButton, true, "Encerrando…");
    stopTimers();
    hideToken();
    const { confirmed } = await logout();
    session = null;
    location.assign(`index.html?sessao=${confirmed ? "encerrada" : "encerrada-local"}`);
});

/* Timers podem atrasar em abas em segundo plano: confere ao voltar. */
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState !== "visible" || !session) return;
    const remaining = msUntilExpiry(session);
    if (remaining !== null && remaining <= 0) renewOnExpiry();
});

/* Inicialização ------------------------------------------------------------ */

initTheme();
initNav();
loadAccount({ initial: true });

