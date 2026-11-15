"""Configuração dos testes.

A SECRET_KEY precisa existir ANTES de importar o backend (a configuração é
validada na importação). Cada sessão de testes gera uma chave aleatória.
O cliente usa https://testserver para que os cookies Secure/__Host- sejam
devolvidos, como num navegador em HTTPS.
"""

import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ["SECRET_KEY"] = secrets.token_urlsafe(48)
os.environ.setdefault("COOKIE_SECURE", "true")
os.environ.setdefault("TRUSTED_PROXY_HOPS", "0")
os.environ.setdefault("HSTS_ENABLED", "false")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from backend.core.config import settings  # noqa: E402
from backend.dependencies import dependencies as deps  # noqa: E402
from backend.main import app  # noqa: E402



@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    """Estado em memória zerado e configuração restaurada a cada teste."""
    deps.user_repository_instance.clear()
    deps.token_service_instance.reset()
    deps.login_rate_limiter_instance.reset()
    yield
    deps.user_repository_instance.clear()
    deps.token_service_instance.reset()
    deps.login_rate_limiter_instance.reset()


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


@pytest.fixture
def cookie_names():
    from backend.core.cookies import cookie_names as names

    return names(settings)

