/* ============================================================
   home.js — Lógica da Página Home / Dashboard (home.html)
   Perfil, /me, token JWT, sessão, logout
   AuthService · Dark Industrial Terminal
   ============================================================ */

"use strict";

const HomePage = (() => {
    /* Estado local da página */
    const state = {
        token: null,
        pass: null,
    };

    /* ── Inicialização ───────────────────────────────────────── */

    function init() {
        state.token = Utils.Session.token;
        state.pass = Utils.Session.pass;

        const noSession = document.getElementById("no-session");
        const cardsGrid = document.querySelector(".cards-grid");
        const profileHero = document.querySelector(".profile-hero");

        if (!state.token) {
            // Sem sessão — exibe estado vazio
            noSession?.classList.add("show");
            if (cardsGrid) cardsGrid.style.display = "none";
            if (profileHero) profileHero.style.display = "none";
            return;
        }

        // Sessão ativa — carrega dados
        _setSessionInfo();
        _showToken();
        loadMe();
    }

    /* ── Carregar dados de /me ───────────────────────────────── */

    async function loadMe() {
        if (!state.token) return;
        Utils.setBtn("btn-me", true, "buscando...");

        try {
            const res = await fetch(`${Utils.getBaseUrl()}/me`, {
                headers: { Authorization: `Bearer ${state.token}` },
            });
            const data = await res.json();

            if (res.ok) {
                _populateProfile(data);
                Utils.showPageAlert(
                    "home-alert",
                    `✓ dados carregados — ${data.email || ""}`,
                    "success",
                );
            } else {
                Utils.showPageAlert(
                    "home-alert",
                    `✗ ${Utils.parseApiError(data)}`,
                    "error",
                );
            }
        } catch (err) {
            Utils.showPageAlert(
                "home-alert",
                `✗ falha: ${err.message}`,
                "error",
            );
        } finally {
            Utils.setBtn("btn-me", false, "↻ Atualizar");
        }
    }

    /* ── Preenche dados do perfil ────────────────────────────── */

    function _populateProfile(data) {
        // Backend retorna apenas id e email — usa email como nome de exibição
        const email = data.email || Utils.Session.email || "—";
        const id = data.id !== undefined ? String(data.id) : "—";
        // Extrai a parte antes do @ para usar como nome de exibição
        const displayName = email.includes("@") ? email.split("@")[0] : email;

        Utils.setText("hero-name", displayName);
        Utils.setText("hero-email", email);
        Utils.setText("d-id", id);
        Utils.setText("d-name", displayName);
        Utils.setText("d-email", email);

        // Badge de autenticado
        const badge = document.getElementById("hero-badge");
        if (badge) {
            badge.textContent = "AUTENTICADO";
            badge.classList.add("on");
        }

        // Dot online
        document.getElementById("online-dot")?.classList.add("on");

        // Senha real (apenas para exibição)
        const passReal = document.getElementById("pass-real");
        if (passReal && state.pass) passReal.textContent = state.pass;
    }

    /* ── Token JWT ───────────────────────────────────────────── */

    function _showToken() {
        const box = document.getElementById("token-box");
        if (!box || !state.token) return;
        box.textContent = state.token;

        const tag = document.getElementById("token-tag");
        if (tag) tag.textContent = "30min · HS256";
    }

    function copyToken() {
        const token = state.token || Utils.Session.token;
        if (!token) return;

        navigator.clipboard.writeText(token).then(() => {
            const tag = document.getElementById("token-tag");
            if (tag) {
                const prev = tag.textContent;
                tag.textContent = "✓ copiado";
                setTimeout(() => {
                    tag.textContent = prev;
                }, 1800);
            }
        });
    }

    /* ── Informações de Sessão ───────────────────────────────── */

    function _setSessionInfo() {
        Utils.setText("sess-status", "ATIVA");
        Utils.setText("sess-expire", "30min após o login");
        Utils.setText("sess-origin", window.location.origin);
    }

    /* ── Mostrar/ocultar senha ───────────────────────────────── */

    function togglePassView() {
        const mask = document.getElementById("pass-mask");
        const real = document.getElementById("pass-real");
        const icon = document.getElementById("pass-eye-icon");
        if (!mask || !real) return;

        const isHidden = real.style.display === "none";
        mask.style.display = isHidden ? "none" : "inline";
        real.style.display = isHidden ? "inline" : "none";

        if (icon) {
            icon.className = isHidden
                ? "fa-regular fa-eye-slash"
                : "fa-regular fa-eye";
        }
    }

    /* ── Logout ──────────────────────────────────────────────── */

    function logout() {
        Utils.Session.clear();
        state.token = null;
        state.pass = null;
        location.href = "index.html";
    }

    return { init, loadMe, copyToken, togglePassView, logout };
})();

/* ── Expõe globalmente para uso inline no HTML ─────────────── */
function loadMe() {
    HomePage.loadMe();
}
function copyToken() {
    HomePage.copyToken();
}
function togglePassView() {
    HomePage.togglePassView();
}
function logout() {
    HomePage.logout();
}

/* ── Boot ──────────────────────────────────────────────────── */
window.addEventListener("DOMContentLoaded", () => {
    Nav.init();
    HomePage.init();
});
