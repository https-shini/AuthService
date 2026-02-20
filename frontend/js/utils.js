/* ============================================================
   utils.js — Utilitários Compartilhados
   Helpers usados em múltiplas páginas
   AuthService · Dark Industrial Terminal
   ============================================================ */

"use strict";

const Utils = (() => {
    /* ── DOM Helpers ─────────────────────────────────────────── */

    /** Define o textContent de um elemento pelo ID */
    function setText(id, value) {
        const el = document.getElementById(id);
        if (el) el.textContent = String(value);
    }

    /** Alias semântico para setText */
    function setEl(id, value) {
        setText(id, value);
    }

    /** Retorna um elemento pelo ID (null-safe shorthand) */
    function el(id) {
        return document.getElementById(id);
    }

    /* ── Botão de Loading ────────────────────────────────────── */

    /** Coloca/retira estado de carregamento num botão */
    function setBtn(id, loading, label) {
        const btn = el(id);
        if (!btn) return;
        btn.disabled = loading;
        btn.textContent = label;
    }

    /* ── Alertas ─────────────────────────────────────────────── */

    /** Exibe alerta inline (dentro de formulário) */
    function showAlert(id, msg, type) {
        const element = el(id);
        if (!element) return;
        element.innerHTML = msg;
        element.className = `alert show ${type}`;
    }

    /** Remove alerta inline */
    function clearAlert(id) {
        const element = el(id);
        if (!element) return;
        element.className = "alert";
        element.innerHTML = "";
    }

    /** Exibe alerta de página (temporário, 4s) */
    function showPageAlert(id, msg, type) {
        const element = el(id);
        if (!element) return;
        element.innerHTML = msg;
        element.className = `alert page-alert show ${type}`;
        setTimeout(() => element.classList.remove("show"), 4000);
    }

    /* ── Toggle de Senha ─────────────────────────────────────── */

    /** Alterna visibilidade do campo de senha e ícone */
    function toggleEye(inputId, btn) {
        const input = el(inputId);
        if (!input) return;
        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        const icon = btn.querySelector("i");
        if (icon) {
            icon.className = isPassword
                ? "fa-regular fa-eye-slash"
                : "fa-regular fa-eye";
        }
    }

    /* ── Enter para Submeter ─────────────────────────────────── */

    /** Dispara uma função ao pressionar Enter num campo */
    function bindEnter(inputId, callback) {
        const input = el(inputId);
        if (input) {
            input.addEventListener("keydown", (e) => {
                if (e.key === "Enter") callback();
            });
        }
    }

    /* ── Parser de Erros FastAPI ─────────────────────────────── */

    /** Extrai mensagem legível do payload de erro FastAPI */
    function parseApiError(data) {
        if (!data || !data.detail) return "erro desconhecido.";
        if (typeof data.detail === "string") return data.detail;
        if (Array.isArray(data.detail)) {
            return data.detail
                .map((e) => {
                    const field = Array.isArray(e.loc)
                        ? e.loc[e.loc.length - 1]
                        : "";
                    return field ? `[${field.toUpperCase()}] ${e.msg}` : e.msg;
                })
                .join(" · ");
        }
        return JSON.stringify(data.detail);
    }

    /* ── Timestamp ───────────────────────────────────────────── */

    /** Retorna horário atual formatado HH:MM:SS */
    function timestamp() {
        return new Date().toLocaleTimeString("pt-BR", { hour12: false });
    }

    /* ── Session Storage com fallback em memória ─────────────── */
    // Usa sessionStorage quando disponível, caso contrário usa objeto em memória.
    // Isso evita erros em contextos onde o storage está bloqueado.

    const _memStore = {};

    const _storage = {
        getItem(key) {
            try {
                return sessionStorage.getItem(key);
            } catch {
                return _memStore[key] ?? null;
            }
        },
        setItem(key, value) {
            try {
                sessionStorage.setItem(key, value);
            } catch {
                _memStore[key] = value;
            }
        },
        clear() {
            try {
                sessionStorage.clear();
            } catch {
                Object.keys(_memStore).forEach((k) => delete _memStore[k]);
            }
        },
    };

    const Session = {
        get token() {
            return _storage.getItem("auth_token");
        },
        get pass() {
            return _storage.getItem("auth_pass");
        },
        get email() {
            return _storage.getItem("auth_email");
        },

        save(token, pass, email) {
            _storage.setItem("auth_token", token);
            _storage.setItem("auth_pass", pass);
            _storage.setItem("auth_email", email);
        },

        clear() {
            _storage.clear();
        },
    };

    /* ── Base URL ────────────────────────────────────────────── */

    /** Retorna a origem da aplicação (funciona local e no Render) */
    function getBaseUrl() {
        return window.location.origin;
    }

    return {
        setText,
        setEl,
        el,
        setBtn,
        showAlert,
        clearAlert,
        showPageAlert,
        toggleEye,
        bindEnter,
        parseApiError,
        timestamp,
        Session,
        getBaseUrl,
    };
})();

// Expõe funções comuns usadas via onclick no HTML
function toggleEye(id, btn) {
    Utils.toggleEye(id, btn);
}
