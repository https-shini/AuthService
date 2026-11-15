/* ==========================================================================
   core/theme.js — Alternância e persistência de tema
   O tema inicial já foi aplicado por theme-init.js; aqui só ligamos os
   botões e acompanhamos a preferência do sistema enquanto o usuário não
   tiver escolhido um tema explicitamente.
   ========================================================================== */

const STORAGE_KEY = "auth_theme";
const THEMES = new Set(["dark", "light"]);
const root = document.documentElement;
const systemLight = window.matchMedia("(prefers-color-scheme: light)");

function readSaved() {
    try {
        const value = window.localStorage.getItem(STORAGE_KEY);
        return THEMES.has(value) ? value : null;
    } catch {
        return null;
    }
}

function save(theme) {
    try {
        window.localStorage.setItem(STORAGE_KEY, theme);
    } catch {
        /* Sem storage a escolha vale só para esta página. */
    }
}

function systemTheme() {
    return systemLight.matches ? "light" : "dark";
}

export function currentTheme() {
    return root.dataset.theme === "light" ? "light" : "dark";
}

function syncToggles() {
    const label =
        currentTheme() === "dark" ? "Ativar tema claro" : "Ativar tema escuro";
    for (const button of document.querySelectorAll("[data-theme-toggle]")) {
        button.setAttribute("aria-label", label);
        button.title = label;
    }
}

export function applyTheme(theme, { persist = false } = {}) {
    const next = THEMES.has(theme) ? theme : "dark";
    root.dataset.theme = next;
    if (persist) save(next);
    syncToggles();
}

export function initTheme() {
    applyTheme(readSaved() ?? systemTheme());

    for (const button of document.querySelectorAll("[data-theme-toggle]")) {
        button.addEventListener("click", () => {
            applyTheme(currentTheme() === "dark" ? "light" : "dark", {
                persist: true,
            });
        });
    }

    systemLight.addEventListener("change", () => {
        if (!readSaved()) applyTheme(systemTheme());
    });
}
