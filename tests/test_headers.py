"""Headers de segurança (item F)."""

import re
from pathlib import Path

import pytest

from backend.core.config import settings
from backend.core.security_headers import FRONTEND_CSP
from helpers import bearer, login, register

FRONTEND = Path(__file__).resolve().parents[1] / "frontend"
PAGES = ["index.html", "home.html", "status.html"]

COMMON = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "cross-origin-opener-policy": "same-origin",
}


@pytest.mark.parametrize("path", ["/", "/index.html", "/home.html", "/status.html", "/health", "/css/tokens.css", "/js/core/api.js", "/docs"])
def test_headers_comuns_em_todas_as_respostas(client, path):
    response = client.get(path)
    assert response.status_code == 200
    for name, value in COMMON.items():
        assert response.headers[name] == value, (path, name)
    assert "camera=()" in response.headers["permissions-policy"]


@pytest.mark.parametrize("page", PAGES)
def test_csp_das_paginas_e_a_meta_mais_frame_ancestors(client, page):
    header = client.get(f"/{page}").headers["content-security-policy"]
    assert header == f"{FRONTEND_CSP}; frame-ancestors 'none'"


@pytest.mark.parametrize("page", PAGES)
def test_meta_csp_do_html_e_identica_a_do_servidor(page):
    """Evita divergência entre a CSP do <meta> e a do header."""
    html = (FRONTEND / page).read_text(encoding="utf-8")
    match = re.search(r'http-equiv="Content-Security-Policy"\s+content="([^"]+)"', html)
    assert match, page
    assert match.group(1) == FRONTEND_CSP


def test_api_json_recebe_csp_restritiva(client):
    assert client.get("/health").headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"


def test_docs_continua_funcionando(client):
    response = client.get("/docs")
    assert response.status_code == 200 and "swagger" in response.text.lower()
    assert response.headers["content-security-policy"] == "frame-ancestors 'none'"


def test_rotas_de_autenticacao_nao_sao_cacheadas(client):
    register(client, "cache@ex.com")
    token = login(client, "cache@ex.com")
    assert token.headers["cache-control"] == "no-store"
    assert client.get("/me", headers=bearer(token.json()["access_token"])).headers["cache-control"] == "no-store"
    assert "no-store" not in client.get("/css/tokens.css").headers.get("cache-control", "")


def test_hsts_desligado_por_padrao(client):
    assert "strict-transport-security" not in client.get("/health").headers


def test_hsts_so_em_https(client, monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setattr(settings, "HSTS_ENABLED", True)
    assert client.get("/health").headers["strict-transport-security"] == f"max-age={settings.HSTS_MAX_AGE}"
    with TestClient(app, base_url="http://testserver") as plain:
        assert "strict-transport-security" not in plain.get("/health").headers


def test_hsts_atras_de_proxy_usa_x_forwarded_proto(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    monkeypatch.setattr(settings, "HSTS_ENABLED", True)
    with TestClient(app, base_url="http://testserver") as plain:
        # Sem proxy confiável o header do cliente é ignorado.
        assert "strict-transport-security" not in plain.get("/health", headers={"X-Forwarded-Proto": "https"}).headers
        monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
        assert "strict-transport-security" in plain.get("/health", headers={"X-Forwarded-Proto": "https"}).headers
