/* ============================================================
   auth.js — Lógica da Página de Acesso (index.html)
   Registro, login, toggle de formulários, força de senha
   AuthService · Dark Industrial Terminal
   ============================================================ */

"use strict";

const AuthPage = (() => {
    /* ── Inicialização ───────────────────────────────────────── */

    function init() {
        _initToggle();
        _initPasswordStrength();
        _initKeyboardShortcuts();
    }

    /* ── Toggle desktop/mobile entre login e cadastro ────────── */

    function _initToggle() {
        const container = document.getElementById("auth-container");
        const btnRegDesk = document.getElementById("btn-show-register");
        const btnLogDesk = document.getElementById("btn-show-login");
        const btnRegMob = document.getElementById("btnR-mob");
        const btnLogMob = document.getElementById("btnL-mob");

        if (!container) return;

        const showRegister = () => container.classList.add("active");
        const showLogin = () => container.classList.remove("active");

        if (btnRegDesk) btnRegDesk.addEventListener("click", showRegister);
        if (btnLogDesk) btnLogDesk.addEventListener("click", showLogin);
        if (btnRegMob) btnRegMob.addEventListener("click", showRegister);
        if (btnLogMob) btnLogMob.addEventListener("click", showLogin);
    }

    /* ── Medidor de força de senha ───────────────────────────── */

    function _initPasswordStrength() {
        const input = document.getElementById("reg-pass");
        if (input) input.addEventListener("input", _updateStrength);
    }

    function _updateStrength() {
        const value = document.getElementById("reg-pass")?.value || "";
        const fill = document.getElementById("strength-fill");
        const label = document.getElementById("strength-label");
        if (!fill || !label) return;

        let score = 0;
        if (value.length >= 8) score++;
        if (/[A-Z]/.test(value)) score++;
        if (/[0-9]/.test(value)) score++;
        if (/[^A-Za-z0-9]/.test(value)) score++;
        if (value.length >= 14) score++;

        const levels = [
            { pct: "0%", bg: "transparent", txt: "", color: "" },
            { pct: "20%", bg: "#f87171", txt: "FRACA", color: "#f87171" },
            { pct: "45%", bg: "#fbbf24", txt: "RAZOÁVEL", color: "#fbbf24" },
            { pct: "65%", bg: "#facc15", txt: "BOA", color: "#facc15" },
            { pct: "85%", bg: "#4ade80", txt: "FORTE", color: "#4ade80" },
            { pct: "100%", bg: "#22c55e", txt: "EXCELENTE", color: "#22c55e" },
        ];

        const lvl = levels[Math.min(score, levels.length - 1)];
        fill.style.width = lvl.pct;
        fill.style.background = lvl.bg;
        label.textContent = lvl.txt;
        label.style.color = lvl.color;
    }

    /* ── Atalhos de teclado (Enter para submeter) ────────────── */

    function _initKeyboardShortcuts() {
        Utils.bindEnter("reg-pass", register);
        Utils.bindEnter("log-pass", login);
    }

    /* ── Registro ────────────────────────────────────────────── */

    async function register() {
        Utils.clearAlert("reg-alert");

        const email = (
            document.getElementById("reg-email")?.value || ""
        ).trim();
        const password = document.getElementById("reg-pass")?.value || "";

        if (!email)
            return Utils.showAlert(
                "reg-alert",
                "// erro: informe seu e-mail.",
                "error",
            );
        if (!password)
            return Utils.showAlert(
                "reg-alert",
                "// erro: informe sua senha.",
                "error",
            );

        Utils.setBtn("btn-reg", true, "aguarde...");

        try {
            const res = await fetch(`${Utils.getBaseUrl()}/register`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                // Envia apenas email e password — o que o backend aceita
                body: JSON.stringify({ email, password }),
            });
            const data = await res.json();

            if (res.ok) {
                Utils.showAlert(
                    "reg-alert",
                    `✓ conta criada — ${data.email}. faça login.`,
                    "success",
                );
                _clearRegisterForm();
            } else {
                Utils.showAlert(
                    "reg-alert",
                    `✗ ${Utils.parseApiError(data)}`,
                    "error",
                );
            }
        } catch (err) {
            Utils.showAlert(
                "reg-alert",
                `✗ conexão falhou: ${err.message}`,
                "error",
            );
        } finally {
            Utils.setBtn("btn-reg", false, "Cadastrar");
        }
    }

    function _clearRegisterForm() {
        ["reg-email", "reg-pass"].forEach((id) => {
            const input = document.getElementById(id);
            if (input) input.value = "";
        });

        const fill = document.getElementById("strength-fill");
        const label = document.getElementById("strength-label");
        if (fill) {
            fill.style.width = "0%";
            fill.style.background = "transparent";
        }
        if (label) {
            label.textContent = "";
        }
    }

    /* ── Login ───────────────────────────────────────────────── */

    async function login() {
        Utils.clearAlert("log-alert");

        const email = (
            document.getElementById("log-email")?.value || ""
        ).trim();
        const password = document.getElementById("log-pass")?.value || "";

        if (!email)
            return Utils.showAlert(
                "log-alert",
                "// erro: informe seu e-mail.",
                "error",
            );
        if (!password)
            return Utils.showAlert(
                "log-alert",
                "// erro: informe sua senha.",
                "error",
            );

        Utils.setBtn("btn-log", true, "autenticando...");

        try {
            const body = new URLSearchParams({ username: email, password });
            const res = await fetch(`${Utils.getBaseUrl()}/token`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                body,
            });
            const data = await res.json();

            if (res.ok) {
                Utils.Session.save(data.access_token, password, email);
                Utils.showAlert(
                    "log-alert",
                    "✓ autenticado — redirecionando...",
                    "success",
                );
                setTimeout(() => {
                    location.href = "home.html";
                }, 900);
            } else {
                Utils.showAlert(
                    "log-alert",
                    `✗ ${Utils.parseApiError(data)}`,
                    "error",
                );
            }
        } catch (err) {
            Utils.showAlert(
                "log-alert",
                `✗ conexão falhou: ${err.message}`,
                "error",
            );
        } finally {
            Utils.setBtn("btn-log", false, "Entrar");
        }
    }

    return { init, register, login };
})();

// Expõe globalmente para uso em onclick no HTML
function registerUser() {
    AuthPage.register();
}
function loginUser() {
    AuthPage.login();
}

// Boot
window.addEventListener("DOMContentLoaded", () => {
    Nav.init();
    AuthPage.init();
});
