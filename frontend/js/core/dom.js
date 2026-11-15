/* ==========================================================================
   core/dom.js — Helpers de DOM seguros e formatação
   --------------------------------------------------------------------------
   Regra do projeto: nenhum dado vindo da API, do token ou do usuário passa
   por innerHTML. Tudo entra como texto (textContent / nós de texto) em
   elementos criados com createElement. `h()` aceita strings como filhos e
   as insere como nós de texto, nunca como HTML.
   ========================================================================== */

const SVG_NS = "http://www.w3.org/2000/svg";
const ICON_SPRITE = "public/icons.svg";

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [
    ...root.querySelectorAll(selector),
];

/** Define o texto de um elemento (por id ou referência). */
export function setText(target, value) {
    const element =
        typeof target === "string" ? document.getElementById(target) : target;
    if (element) element.textContent = value == null ? "" : String(value);
    return element;
}

/**
 * Cria um elemento. Props especiais: className, text, dataset.
 * As demais viram atributos (true → atributo vazio; null/false → omitido).
 */
export function h(tag, props = {}, children = []) {
    const element = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
        if (value == null || value === false) continue;
        if (key === "className") element.className = value;
        else if (key === "text") element.textContent = String(value);
        else if (key === "dataset") Object.assign(element.dataset, value);
        else element.setAttribute(key, value === true ? "" : String(value));
    }
    const list = Array.isArray(children) ? children : [children];
    element.append(...list.filter((child) => child != null && child !== false));
    return element;
}

/** Ícone do sprite, sempre decorativo (o texto ao lado carrega o sentido). */
export function icon(name, className = "") {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", `icon icon--${name} ${className}`.trim());
    svg.setAttribute("aria-hidden", "true");
    svg.setAttribute("focusable", "false");
    const use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", `${ICON_SPRITE}#${name}`);
    svg.append(use);
    return svg;
}

/* Alertas ----------------------------------------------------------------- */

const ALERT_ICONS = {
    success: "check-circle",
    error: "alert-circle",
    warning: "alert-triangle",
    info: "info",
};

/**
 * Mostra um alerta dentro de uma região já presente no HTML (que carrega
 * role="status" ou role="alert"; a região precisa existir antes do
 * conteúdo para o leitor de tela anunciar a mudança).
 */
export function showAlert(
    region,
    { type = "info", title, message, list = [], action },
) {
    if (!region) return;
    const content = h("div", { className: "alert__content" }, [
        title ? h("p", { className: "alert__title", text: title }) : null,
        message ? h("p", { text: message }) : null,
        list.length
            ? h(
                  "ul",
                  { className: "alert__list" },
                  list.map((item) => h("li", { text: item })),
              )
            : null,
        // Ação opcional: só links internos, montados como elemento.
        action
            ? h("p", { className: "alert__actions" }, [
                  h("a", {
                      className: "btn btn--outline btn--sm",
                      href: action.href,
                      text: action.label,
                  }),
              ])
            : null,
    ]);
    region.replaceChildren(
        h("div", { className: `alert alert--${type}` }, [
            icon(ALERT_ICONS[type] ?? "info"),
            content,
        ]),
    );
}

export function clearAlert(region) {
    region?.replaceChildren();
}

/* Botões ------------------------------------------------------------------ */

/**
 * Estado de carregamento: desabilita o botão (impede envio duplicado),
 * marca aria-busy e troca só o rótulo (.btn__label), preservando ícones.
 */
export function setBusy(button, busy, busyLabel) {
    if (!button) return;
    const label = button.querySelector(".btn__label");
    if (busy) {
        if (label && button.dataset.idleLabel === undefined) {
            button.dataset.idleLabel = label.textContent;
        }
        if (label && busyLabel) label.textContent = busyLabel;
        button.setAttribute("aria-busy", "true");
        button.disabled = true;
    } else {
        if (label && button.dataset.idleLabel !== undefined) {
            label.textContent = button.dataset.idleLabel;
        }
        delete button.dataset.idleLabel;
        button.removeAttribute("aria-busy");
        button.disabled = false;
    }
}

/* Área de transferência ----------------------------------------------------- */

export async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        return true;
    } catch {
        return false;
    }
}

/* Formatação (pt-BR) ------------------------------------------------------ */

const timeFormat = new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
});

const dateTimeFormat = new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
});

export const formatTime = (date) => timeFormat.format(date);
export const formatDateTime = (date) => dateTimeFormat.format(date);

/** Duração legível: "45 s", "12 min", "1 h 05 min". */
export function formatDuration(ms) {
    if (!Number.isFinite(ms) || ms <= 0) return "0 s";
    if (ms < 60_000) return `${Math.ceil(ms / 1000)} s`;
    const totalMinutes = Math.floor(ms / 60_000);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    return hours
        ? `${hours} h ${String(minutes).padStart(2, "0")} min`
        : `${minutes} min`;
}
