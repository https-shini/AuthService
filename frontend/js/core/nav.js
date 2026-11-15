/* ==========================================================================
   core/nav.js — Menu móvel acessível
   Botão com aria-expanded/aria-controls; fecha com Escape (devolvendo o
   foco ao botão), com clique fora, ao escolher um link e quando a janela
   passa a mostrar a navegação de desktop (640px, ver layout.css).
   ========================================================================== */

const DESKTOP_NAV = window.matchMedia("(min-width: 640px)");

export function initNav() {
    const toggle = document.querySelector("[data-nav-toggle]");
    const menu = toggle
        ? document.getElementById(toggle.getAttribute("aria-controls"))
        : null;
    if (!toggle || !menu) return;

    const isOpen = () => toggle.getAttribute("aria-expanded") === "true";

    const setOpen = (open, { returnFocus = false } = {}) => {
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
        menu.hidden = !open;
        if (!open && returnFocus) toggle.focus();
    };

    setOpen(false);

    toggle.addEventListener("click", () => setOpen(!isOpen()));

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && isOpen()) {
            setOpen(false, { returnFocus: true });
        }
    });

    document.addEventListener("click", (event) => {
        if (
            isOpen() &&
            !toggle.contains(event.target) &&
            !menu.contains(event.target)
        ) {
            setOpen(false);
        }
    });

    menu.addEventListener("click", (event) => {
        if (event.target.closest("a")) setOpen(false);
    });

    DESKTOP_NAV.addEventListener("change", (event) => {
        if (event.matches) setOpen(false);
    });
}
