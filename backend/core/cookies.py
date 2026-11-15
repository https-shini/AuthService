"""Cookies da sessão (refresh e CSRF).

Com COOKIE_SECURE (padrão), os nomes levam o prefixo `__Host-`: o
navegador só aceita esses cookies com Secure, Path=/ e sem Domain, o que
impede que outro subdomínio os sobrescreva. Sem Secure (HTTP fora de
localhost), o prefixo não é permitido e os nomes ficam sem ele.

* refresh — HttpOnly: JavaScript não lê.
* CSRF    — legível pelo frontend, que o devolve em X-CSRF-Token.
Ambos SameSite=Strict e sem Max-Age (somem ao fechar o navegador; o
prazo real da sessão é controlado no servidor).
"""

from dataclasses import dataclass

from starlette.responses import Response

from backend.core.config import Settings
from backend.services.token_service import IssuedTokens

CSRF_HEADER = "X-CSRF-Token"


@dataclass(frozen=True)
class CookieNames:
    refresh: str
    csrf: str


def cookie_names(settings: Settings) -> CookieNames:
    prefix = "__Host-" if settings.COOKIE_SECURE else ""
    return CookieNames(refresh=f"{prefix}auth_refresh", csrf=f"{prefix}auth_csrf")


def set_session_cookies(response: Response, issued: IssuedTokens, settings: Settings) -> None:
    names = cookie_names(settings)
    common = {"secure": settings.COOKIE_SECURE, "samesite": "strict", "path": "/"}
    response.set_cookie(names.refresh, issued.refresh_token, httponly=True, **common)
    response.set_cookie(names.csrf, issued.csrf_token, httponly=False, **common)


def clear_session_cookies(response: Response, settings: Settings) -> None:
    names = cookie_names(settings)
    for name, httponly in ((names.refresh, True), (names.csrf, False)):
        response.delete_cookie(name, path="/", secure=settings.COOKIE_SECURE, httponly=httponly, samesite="strict")
