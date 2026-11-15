/* ==========================================================================
   pages/status.js — Status da API (status.html)
   --------------------------------------------------------------------------
   Todo indicador reflete uma consulta real feita por este navegador:
     · GET /health → disponibilidade geral (é o que define o resumo);
     · GET /me     → só com sessão; sem token fica "não verificado".
   /register e /token não são consultados (criariam usuários ou tentativas
   de login) e permanecem "não verificado" no HTML.

   Estados: ok · down (erro HTTP) · auth (401) · comm (rede/timeout) ·
   idle (não verificado) · checking (em andamento).
   ========================================================================== */

import { api, ErrorKind } from "../core/api.js";
import { getSession, clearSession } from "../core/session.js";
import { $, $$, h, setText, setBusy, formatTime } from "../core/dom.js";
import { initTheme } from "../core/theme.js";
import { initNav } from "../core/nav.js";

const HISTORY_LIMIT = 50;

const REASON_PHRASES = {
    200: "OK",
    400: "Bad Request",
    401: "Unauthorized",
    404: "Not Found",
    422: "Unprocessable Content",
    500: "Internal Server Error",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
};

const STATE_LABELS = {
    ok: "Disponível",
    down: "Indisponível",
    auth: "Falha de autenticação",
    comm: "Falha de comunicação",
    idle: "Não verificado",
    checking: "Verificando…",
};

const httpLabel = (status) =>
    status ? `${status} ${REASON_PHRASES[status] ?? ""}`.trim() : "sem resposta";

/* Classificação de um resultado de request() em estado. */
function classify(result) {
    if (result.ok) return "ok";
    if (result.status === 0) return "comm";
    if (result.error?.kind === ErrorKind.UNAUTHORIZED) return "auth";
    return "down";
}

/* Cartões de endpoint ----------------------------------------------------- */

function setEndpoint(key, state, label = STATE_LABELS[state]) {
    $(`#ep-${key}-dot`).dataset.state = state;
    setText(`ep-${key}-state`, label);
}

function recordMeasurement(key, result, at) {
    setText(`ep-${key}-http`, httpLabel(result.status));
    setText(`ep-${key}-ms`, `${result.durationMs} ms`);
    setText(`ep-${key}-time`, formatTime(at));
}

/* Resumo (derivado de /health) -------------------------------------------- */

function setSummary(state, title, detail) {
    $("#summary-dot").dataset.state = state;
    setText("summary-title", title);
    setText("summary-detail", detail);
}

/* Histórico (apenas em memória, desta visita) ----------------------------- */

const historyBody = $("#history-body");
const historyEmpty = $("#history-empty");

function addHistory({ at, endpoint, state, result }) {
    const row = h("tr", {}, [
        h("td", { "data-label": "Horário", text: formatTime(at) }),
        h("td", { "data-label": "Endpoint", text: endpoint }),
        h("td", { "data-label": "Resultado" }, [
            h("span", { className: "history__result" }, [
                h("span", { className: "status-dot", dataset: { state } }),
                STATE_LABELS[state],
            ]),
        ]),
        h("td", { "data-label": "HTTP", text: httpLabel(result.status) }),
        h("td", { "data-label": "Tempo", text: `${result.durationMs} ms` }),
    ]);
    historyBody.prepend(row);
    while (historyBody.rows.length > HISTORY_LIMIT) historyBody.lastElementChild.remove();
    historyEmpty.hidden = true;
}

function clearHistory() {
    historyBody.replaceChildren();
    historyEmpty.hidden = false;
}

/* Verificações ------------------------------------------------------------- */

async function checkHealth() {
    setEndpoint("health", "checking");
    setSummary("checking", "Verificando…", "Consultando GET /health.");

    const result = await api.health();
    const at = new Date();
    let state = classify(result);
    // 200 sem o corpo do contrato não conta como disponível.
    if (state === "ok" && result.data?.status !== "ok") state = "down";

    setEndpoint("health", state);
    recordMeasurement("health", result, at);
    addHistory({ at, endpoint: "GET /health", state, result });

    if (state === "ok") {
        setSummary(
            "ok",
            "Operacional",
            `GET /health respondeu ${httpLabel(result.status)} em ${result.durationMs} ms, às ${formatTime(at)}.`,
        );
    } else if (state === "comm") {
        setSummary("comm", "Sem comunicação", `${result.error.message} Última tentativa às ${formatTime(at)}.`);
    } else {
        setSummary(
            "down",
            "Indisponível",
            `GET /health respondeu ${httpLabel(result.status)} às ${formatTime(at)}.`,
        );
    }
    return state;
}

async function checkMe() {
    const note = $("#ep-me-note");
    const session = getSession();

    if (!session) {
        setEndpoint("me", "idle", "Não verificado · sem sessão");
        note.hidden = false;
        return "idle";
    }
    note.hidden = true;
    setEndpoint("me", "checking");

    const result = await api.me(session.token);
    const at = new Date();
    const state = classify(result);

    recordMeasurement("me", result, at);
    addHistory({ at, endpoint: "GET /me", state, result });

    if (state === "auth") {
        // Token recusado: remove a sessão local, como no painel.
        clearSession();
        setEndpoint("me", "auth", "Falha de autenticação · token removido");
    } else {
        setEndpoint("me", state);
    }
    return state;
}

async function runCheck(button, check) {
    if (button?.disabled) return;
    setBusy(button, true, "Verificando…");
    try {
        await check();
    } finally {
        setBusy(button, false);
    }
}

async function checkAll() {
    const button = $("#check-all");
    await runCheck(button, () => Promise.all([checkHealth(), checkMe()]));
}

/* Inicialização ------------------------------------------------------------ */

initTheme();
initNav();

$("#check-all").addEventListener("click", checkAll);
for (const button of $$("[data-check]")) {
    const check = button.dataset.check === "health" ? checkHealth : checkMe;
    button.addEventListener("click", () => runCheck(button, check));
}
$("#history-clear").addEventListener("click", clearHistory);

checkAll();
