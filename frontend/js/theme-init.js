/* ==========================================================================
   theme-init.js — Aplica o tema antes da primeira pintura (anti-flash)
   --------------------------------------------------------------------------
   Carregado SÍNCRONO no <head>, antes das folhas de estilo, e de propósito
   não é módulo: módulos são adiados e a página pintaria no tema errado
   por um instante. Também não é inline, para a CSP não precisar liberar
   scripts inline nem manter hash.

   Ordem de decisão (a mesma do portfólio): escolha salva → preferência do
   sistema → escuro. A chave `auth_theme` é a mesma da versão anterior,
   então quem já escolheu um tema o mantém.
   ========================================================================== */
(function () {
    var theme = "dark";
    try {
        var saved = window.localStorage.getItem("auth_theme");
        if (saved === "dark" || saved === "light") {
            theme = saved;
        } else if (
            window.matchMedia &&
            window.matchMedia("(prefers-color-scheme: light)").matches
        ) {
            theme = "light";
        }
    } catch (error) {
        /* Storage bloqueado: segue com o padrão. */
    }
    document.documentElement.setAttribute("data-theme", theme);
})();
