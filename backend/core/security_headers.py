"""Headers de segurança aplicados a todas as respostas.

CSP
---
* Páginas do frontend: FRONTEND_CSP + `frame-ancestors 'none'`. A
  FRONTEND_CSP é a MESMA política declarada em `<meta>` nos HTML (um teste
  garante que não divirjam). O header só acrescenta `frame-ancestors`,
  que não funciona via `<meta>`. Duas políticas iguais não conflitam.
* /docs e /redoc: o Swagger/ReDoc do FastAPI carrega scripts de CDN e
  inline, então recebem só `frame-ancestors 'none'`.
* Demais respostas (JSON, CSS, JS, SVG): `default-src 'none'` — nada
  nelas deve executar ou carregar recursos.

HSTS só é enviado com HSTS_ENABLED e em requisição HTTPS (inclusive via
proxy confiável, ver `core/network.py`).
"""

from starlette.requests import Request
from starlette.responses import Response

from backend.core.config import Settings
from backend.core.network import is_https

FRONTEND_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' https://api.fontshare.com https://fonts.googleapis.com; "
    "font-src 'self' https://cdn.fontshare.com https://fonts.gstatic.com; "
    "img-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

DOCS_PATHS = ("/docs", "/redoc")
NO_STORE_PATHS = {"/token", "/refresh", "/logout", "/me", "/register"}

STATIC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
}


def content_security_policy(path: str, content_type: str) -> str:
    if path.startswith(DOCS_PATHS):
        return "frame-ancestors 'none'"
    if content_type.startswith("text/html"):
        return f"{FRONTEND_CSP}; frame-ancestors 'none'"
    return "default-src 'none'; frame-ancestors 'none'"


def apply_security_headers(request: Request, response: Response, settings: Settings) -> None:
    for name, value in STATIC_HEADERS.items():
        response.headers.setdefault(name, value)

    content_type = response.headers.get("content-type", "")
    response.headers.setdefault("Content-Security-Policy", content_security_policy(request.url.path, content_type))

    if request.url.path in NO_STORE_PATHS:
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"

    if settings.HSTS_ENABLED and is_https(request, settings.TRUSTED_PROXY_HOPS):
        response.headers["Strict-Transport-Security"] = f"max-age={settings.HSTS_MAX_AGE}"
