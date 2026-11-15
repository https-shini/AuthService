/* ==========================================================================
   pages/auth.js — Página de acesso (index.html)
   Abas Entrar/Criar conta, validação no cliente espelhando o servidor,
   envio sem duplicidade e feedback acessível.

   A senha só existe no campo do formulário e no corpo da requisição:
   não é gravada, registrada em log nem exibida em mensagens. Depois de um
   login bem-sucedido o campo é esvaziado.
   ========================================================================== */

import { api, ErrorKind } from "../core/api.js";
import { saveSession, getSession, isExpired, canRefresh } from "../core/session.js";
import { $, $$, setText, showAlert, clearAlert, setBusy, formatTime, formatDuration } from "../core/dom.js";
import { initTheme } from "../core/theme.js";
import { initNav } from "../core/nav.js";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* Regras de backend/schemas/user_schemas.py (UserCreate): mínimo de 8
   caracteres, ao menos uma letra e ao menos um número. O servidor usa
   str.isalpha/isdigit, que aceitam Unicode; daí \p{L} e \p{Nd}. */
const PASSWORD_RULES = {
    length: (value) => value.length >= 8,
    letter: (value) => /\p{L}/u.test(value),
    digit: (value) => /\p{Nd}/u.test(value),
};

const STRENGTH_LABELS = ["—", "Fraca", "Razoável", "Boa", "Forte", "Excelente"];

// Limites de backend/schemas/user_schemas.py.
const PASSWORD_MAX_BYTES = 72; // bcrypt ignora o que passa disso
const NAME_MAX_LENGTH = 100;
const utf8Length = (value) => new TextEncoder().encode(value).length;

const tabs = { login: $("#tab-login"), register: $("#tab-register") };
const panels = { login: $("#panel-login"), register: $("#panel-register") };

/* Abas --------------------------------------------------------------------- */

function selectTab(name, { focusTab = false, focusField = false } = {}) {
    for (const key of Object.keys(tabs)) {
        const selected = key === name;
        tabs[key].setAttribute("aria-selected", String(selected));
        tabs[key].tabIndex = selected ? 0 : -1;
        panels[key].hidden = !selected;
    }
    if (focusTab) tabs[name].focus();
    if (focusField) panels[name].querySelector("input")?.focus();

    const url = name === "register" ? "#cadastro" : location.pathname + location.search;
    history.replaceState(null, "", url);
}

function initTabs() {
    const order = ["login", "register"];
    for (const [name, tab] of Object.entries(tabs)) {
        tab.addEventListener("click", () => selectTab(name));
        tab.addEventListener("keydown", (event) => {
            const index = order.indexOf(name);
            const moves = {
                ArrowRight: order[(index + 1) % order.length],
                ArrowLeft: order[(index - 1 + order.length) % order.length],
                Home: order[0],
                End: order[order.length - 1],
            };
            if (moves[event.key]) {
                event.preventDefault();
                selectTab(moves[event.key], { focusTab: true });
            }
        });
    }
    for (const button of $$("[data-show-tab]")) {
        button.addEventListener("click", () =>
            selectTab(button.dataset.showTab, { focusField: true }),
        );
    }
    const tabFromHash = () => (location.hash === "#cadastro" ? "register" : "login");
    selectTab(tabFromHash());
    // Link para #cadastro dentro da própria página (mesma URL, só muda o hash).
    window.addEventListener("hashchange", () => selectTab(tabFromHash()));
}

/* Campos ------------------------------------------------------------------- */

function setFieldError(input, message) {
    const error = document.getElementById(`${input.id}-error`);
    if (message) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
    setText(error, message ?? "");
}

function emailError(value) {
    if (!value) return "Informe seu e-mail.";
    if (!EMAIL_PATTERN.test(value)) return "Informe um e-mail válido.";
    return null;
}

function initPasswordToggles() {
    for (const button of $$("[data-password-toggle]")) {
        const input = document.getElementById(button.dataset.passwordToggle);
        button.addEventListener("click", () => {
            const show = input.type === "password";
            input.type = show ? "text" : "password";
            button.setAttribute("aria-pressed", String(show));
            button.setAttribute("aria-label", show ? "Ocultar senha" : "Mostrar senha");
        });
    }
}

function hidePassword(input) {
    input.type = "password";
    const button = $(`[data-password-toggle="${input.id}"]`);
    button?.setAttribute("aria-pressed", "false");
    button?.setAttribute("aria-label", "Mostrar senha");
}

/* Mensagens de erro da API, iguais para os dois formulários. */
function describeFailure(error) {
    if (error.kind === ErrorKind.NETWORK || error.kind === ErrorKind.TIMEOUT) {
        return {
            title: "Sem comunicação com o servidor",
            message: `${error.message} Verifique a conexão e tente novamente.`,
        };
    }
    if (error.kind === ErrorKind.SERVER) {
        return { title: "Erro no servidor", message: error.message };
    }
    return { title: "Não foi possível concluir", message: error.message };
}

/* Mapeia erros de validação (422) para os campos do formulário. */
function applyFieldErrors(error, fieldMap) {
    let applied = false;
    for (const { field, message } of error.fields ?? []) {
        const input = fieldMap[field];
        if (input) {
            setFieldError(input, message);
            applied = true;
        }
    }
    return applied;
}

/* Entrar ------------------------------------------------------------------- */

function initLogin() {
    const form = $("#login-form");
    const email = $("#login-email");
    const password = $("#login-password");
    const submit = $("#login-submit");
    const alert = $("#login-alert");
    let pending = false;

    for (const input of [email, password]) {
        input.addEventListener("input", () => setFieldError(input, null));
    }

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (pending || submit.disabled) return;
        clearAlert(alert);

        const emailValue = email.value.trim();
        const errors = [
            [email, emailError(emailValue)],
            [password, password.value ? null : "Informe sua senha."],
        ];
        for (const [input, message] of errors) setFieldError(input, message);
        const firstInvalid = errors.find(([, message]) => message)?.[0];
        if (firstInvalid) {
            firstInvalid.focus();
            return;
        }

        pending = true;
        setBusy(submit, true, "Entrando…");
        const result = await api.login(emailValue, password.value);

        if (result.ok && typeof result.data?.access_token === "string") {
            password.value = "";
            hidePassword(password);
            saveSession(result.data.access_token);
            showAlert(alert, {
                type: "success",
                title: "Autenticado",
                message: "Redirecionando para o painel…",
            });
            window.setTimeout(() => location.assign("home.html"), 600);
            return; // o botão segue ocupado até a navegação
        }

        pending = false;
        setBusy(submit, false);

        const error = result.error ?? { kind: ErrorKind.HTTP, message: "Resposta inesperada." };
        if (error.kind === ErrorKind.RATE_LIMITED) {
            showAlert(alert, {
                type: "warning",
                title: "Muitas tentativas",
                message: error.retryAfter
                    ? `Por segurança, o login foi pausado após várias tentativas sem sucesso. Tente novamente em ${formatDuration(error.retryAfter * 1000)}.`
                    : error.message,
            });
            if (error.retryAfter) lockButton(submit, error.retryAfter);
            return;
        }
        if (error.kind === ErrorKind.UNAUTHORIZED) {
            showAlert(alert, {
                type: "error",
                title: "Não foi possível entrar",
                message: `${error.message}.`.replace(/\.\.$/, "."),
            });
            password.select();
            return;
        }
        if (error.kind === ErrorKind.VALIDATION &&
            applyFieldErrors(error, { username: email, password })) {
            form.querySelector('[aria-invalid="true"]')?.focus();
            return;
        }
        showAlert(alert, { type: "error", ...describeFailure(error) });
    });
}

/* Bloqueio temporário do botão após 429, com contagem regressiva. */
function lockButton(button, seconds) {
    const label = $(".btn__label", button);
    const idleLabel = label.textContent;
    let remaining = seconds;
    button.disabled = true;
    const tick = () => {
        if (remaining <= 0) {
            window.clearInterval(timer);
            label.textContent = idleLabel;
            button.disabled = false;
            return;
        }
        const minutes = Math.floor(remaining / 60);
        const seconds = String(remaining % 60).padStart(2, "0");
        label.textContent = `Aguarde ${minutes}:${seconds}`;
        remaining -= 1;
    };
    const timer = window.setInterval(tick, 1000);
    tick();
}

/* Criar conta -------------------------------------------------------------- */

function passwordStrength(value) {
    if (!value) return 0;
    let score = 0;
    if (value.length >= 8) score++;
    if (/[A-Z]/.test(value)) score++;
    if (/\d/.test(value)) score++;
    if (/[^A-Za-z0-9]/.test(value)) score++;
    if (value.length >= 14) score++;
    return Math.max(score, 1);
}

function updatePasswordHelp(value) {
    for (const item of $$("#password-rules [data-rule]")) {
        const met = PASSWORD_RULES[item.dataset.rule](value);
        item.dataset.met = String(met);
        setText($("[data-rule-state]", item), met ? "(atendido)" : "(pendente)");
    }
    const level = passwordStrength(value);
    $("#password-meter").dataset.level = String(level);
    setText("password-meter-label", STRENGTH_LABELS[level]);
}

function initRegister() {
    const form = $("#register-form");
    const name = $("#register-name");
    const email = $("#register-email");
    const password = $("#register-password");
    const submit = $("#register-submit");
    const alert = $("#register-alert");
    let pending = false;

    name.addEventListener("input", () => setFieldError(name, null));
    email.addEventListener("input", () => setFieldError(email, null));
    password.addEventListener("input", () => {
        setFieldError(password, null);
        updatePasswordHelp(password.value);
    });
    updatePasswordHelp("");

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (pending) return;
        clearAlert(alert);

        const nameValue = name.value.replace(/\s+/g, " ").trim();
        const emailValue = email.value.trim();
        const unmet = Object.entries(PASSWORD_RULES)
            .filter(([, rule]) => !rule(password.value))
            .map(([rule]) => rule);
        let passwordMessage = null;
        if (!password.value) passwordMessage = "Informe uma senha.";
        else if (unmet.length) passwordMessage = "A senha ainda não atende a todos os requisitos abaixo.";
        else if (utf8Length(password.value) > PASSWORD_MAX_BYTES) {
            passwordMessage = `A senha pode ter no máximo ${PASSWORD_MAX_BYTES} bytes (cerca de ${PASSWORD_MAX_BYTES} caracteres sem acento).`;
        }
        const errors = [
            [name, nameValue.length > NAME_MAX_LENGTH ? `O nome pode ter no máximo ${NAME_MAX_LENGTH} caracteres.` : null],
            [email, emailError(emailValue)],
            [password, passwordMessage],
        ];
        for (const [input, message] of errors) setFieldError(input, message);
        const firstInvalid = errors.find(([, message]) => message)?.[0];
        if (firstInvalid) {
            firstInvalid.focus();
            return;
        }

        pending = true;
        setBusy(submit, true, "Criando conta…");
        const result = await api.register(emailValue, password.value, nameValue || undefined);
        pending = false;
        setBusy(submit, false);

        if (result.ok) {
            const createdEmail = result.data?.email ?? emailValue;
            const greeting = result.data?.name ? `${result.data.name}, sua conta` : "Conta";
            form.reset();
            hidePassword(password);
            updatePasswordHelp("");
            selectTab("login");
            $("#login-email").value = createdEmail;
            showAlert($("#login-alert"), {
                type: "success",
                title: "Conta criada",
                message: `${greeting} foi criada para ${createdEmail}. Agora entre com a sua senha.`,
            });
            $("#login-password").focus();
            return;
        }

        const error = result.error;
        if (error.kind === ErrorKind.BAD_REQUEST) {
            setFieldError(email, `${error.message}. Entre com ele ou use outro e-mail.`);
            email.focus();
            return;
        }
        if (error.kind === ErrorKind.VALIDATION &&
            applyFieldErrors(error, { name, email, password })) {
            form.querySelector('[aria-invalid="true"]')?.focus();
            return;
        }
        showAlert(alert, { type: "error", ...describeFailure(error) });
    });
}

/* Avisos de sessão e status da API -------------------------------------- */

function showSessionNotice() {
    const region = $("#session-notice");
    const params = new URLSearchParams(location.search);
    const reason = params.get("sessao");

    if (reason) {
        params.delete("sessao");
        const query = params.toString();
        history.replaceState(null, "", location.pathname + (query ? `?${query}` : "") + location.hash);
    }

    if (reason === "expirada") {
        showAlert(region, {
            type: "warning",
            title: "Sessão expirada",
            message: "Seu token expirou ou deixou de ser aceito. Entre novamente para continuar.",
        });
        return;
    }
    if (reason === "encerrada-local") {
        showAlert(region, {
            type: "warning",
            title: "Sessão removida deste navegador",
            message: "O servidor não confirmou o encerramento (sem conexão). A sessão expira sozinha no prazo; se estiver em um computador compartilhado, feche o navegador.",
        });
        return;
    }
    if (reason === "encerrada") {
        showAlert(region, {
            type: "success",
            title: "Sessão encerrada",
            message: "A sessão foi revogada no servidor e os dados de autenticação foram removidos deste navegador.",
        });
        return;
    }

    const session = getSession();
    const renewable = canRefresh();
    if (session && !session.malformed && (!isExpired(session) || renewable)) {
        let message = "Há uma sessão ativa neste navegador.";
        if (renewable) message = "A sessão é renovada automaticamente enquanto o navegador estiver aberto.";
        else if (session.expiresAt) message = `A sessão atual vale até ${formatTime(session.expiresAt)}.`;
        showAlert(region, {
            type: "info",
            title: "Você já está conectado",
            message,
            action: { href: "home.html", label: "Ir para o painel" },
        });
    }
}

async function checkApi() {
    const dot = $("#api-dot");
    const label = $("#api-label");
    const result = await api.health();
    if (result.ok && result.data?.status === "ok") {
        dot.dataset.state = "ok";
        setText(label, `API disponível · ${result.durationMs} ms`);
    } else if (result.status === 0) {
        dot.dataset.state = "comm";
        setText(label, "Sem comunicação com a API");
    } else {
        dot.dataset.state = "down";
        setText(label, `API indisponível · HTTP ${result.status}`);
    }
}

/* Inicialização ------------------------------------------------------------ */

initTheme();
initNav();
initTabs();
initPasswordToggles();
initLogin();
initRegister();
showSessionNotice();
checkApi();
