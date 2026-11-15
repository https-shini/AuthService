"""Tokens: expirado, adulterado, revogado, logout, refresh, cookies e CSRF (item C)."""

import base64
import json
import logging
import time

import pytest
from jose import jwt

from backend.core.config import settings
from backend.dependencies import dependencies as deps
from helpers import PASSWORD, FakeClock, bearer, csrf_header, login, register

GENERIC_401 = {"detail": "Não foi possível validar as credenciais"}


@pytest.fixture
def session(client):
    register(client, "tok@ex.com")
    response = login(client, "tok@ex.com")
    assert response.status_code == 200
    return response.json()["access_token"]


def me(client, token):
    return client.get("/me", headers=bearer(token))


def b64(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()


# --- Access token ----------------------------------------------------------


def test_claims_do_access_token(session):
    claims = jwt.get_unverified_claims(session)
    assert claims["sub"] == "tok@ex.com"
    assert claims["type"] == "access"
    assert claims["jti"] and claims["sid"]
    assert claims["exp"] - claims["iat"] == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_token_expirado_e_recusado(client, session):
    claims = jwt.get_unverified_claims(session)
    claims["exp"] = int(time.time()) - 5
    expired = jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    response = me(client, expired)
    assert response.status_code == 401
    assert response.json() == GENERIC_401
    assert response.headers["WWW-Authenticate"] == 'Bearer error="invalid_token"'


def test_token_com_assinatura_adulterada_e_recusado(client, session):
    header, payload, signature = session.split(".")
    tampered = f"{header}.{payload}.{signature[:-4]}{'AAAA' if not signature.endswith('AAAA') else 'BBBB'}"
    assert me(client, tampered).status_code == 401


def test_payload_forjado_e_recusado(client, session):
    register(client, "vitima@ex.com")
    header, payload, signature = session.split(".")
    claims = jwt.get_unverified_claims(session)
    claims["sub"] = "vitima@ex.com"
    assert me(client, f"{header}.{b64(claims)}.{signature}").status_code == 401


def test_alg_none_e_recusado(client, session):
    claims = jwt.get_unverified_claims(session)
    unsigned = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64(claims)}."
    assert me(client, unsigned).status_code == 401


def test_token_do_formato_antigo_sem_jti_e_recusado(client, session):
    """Tokens emitidos antes desta versão (só sub/exp) não podem ser revogados,
    então deixam de ser aceitos. Com usuários em memória eles já não
    sobreviviam a um reinício."""
    old = jwt.encode({"sub": "tok@ex.com", "exp": int(time.time()) + 600}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    assert me(client, old).status_code == 401


def test_token_assinado_com_outra_chave_e_recusado(client, session):
    claims = jwt.get_unverified_claims(session)
    assert me(client, jwt.encode(claims, "x" * 48, algorithm="HS256")).status_code == 401


def test_erro_nunca_ecoa_o_token(client, session):
    garbage = session + "lixo"
    response = me(client, garbage)
    assert garbage not in response.text and session not in response.text


# --- Cookies ----------------------------------------------------------------


def test_login_define_cookies_seguros(client, cookie_names):
    register(client, "ck@ex.com")
    response = login(client, "ck@ex.com")
    cookies = response.headers.get_list("set-cookie")
    refresh = next(c for c in cookies if c.startswith(cookie_names.refresh + "="))
    csrf = next(c for c in cookies if c.startswith(cookie_names.csrf + "="))
    assert cookie_names.refresh.startswith("__Host-")
    for raw in (refresh, csrf):
        lowered = raw.lower()
        assert "secure" in lowered and "samesite=strict" in lowered and "path=/" in lowered
        assert "domain=" not in lowered and "max-age" not in lowered and "expires=" not in lowered
    assert "httponly" in refresh.lower()
    assert "httponly" not in csrf.lower()
    # O refresh token nunca vai no corpo.
    assert set(response.json()) == {"access_token", "token_type"}


def test_sem_cookie_secure_os_nomes_perdem_o_prefixo(monkeypatch):
    from backend.core.cookies import cookie_names

    monkeypatch.setattr(settings, "COOKIE_SECURE", False)
    names = cookie_names(settings)
    assert names.refresh == "auth_refresh" and names.csrf == "auth_csrf"


# --- Refresh ----------------------------------------------------------------


def test_refresh_emite_novo_access_e_rotaciona_os_cookies(client, session, cookie_names):
    old_refresh = client.cookies.get(cookie_names.refresh)
    old_csrf = client.cookies.get(cookie_names.csrf)
    response = client.post("/refresh", headers=csrf_header(client, cookie_names))
    assert response.status_code == 200
    new_token = response.json()["access_token"]
    assert new_token != session
    assert client.cookies.get(cookie_names.refresh) != old_refresh
    assert client.cookies.get(cookie_names.csrf) != old_csrf
    assert me(client, new_token).status_code == 200
    # Mesma sessão (sid), outro jti.
    old_claims, new_claims = jwt.get_unverified_claims(session), jwt.get_unverified_claims(new_token)
    assert old_claims["sid"] == new_claims["sid"] and old_claims["jti"] != new_claims["jti"]


@pytest.mark.parametrize("csrf", [None, "", "valor-errado"])
def test_refresh_sem_csrf_valido_e_recusado_com_403(client, session, cookie_names, csrf):
    headers = {} if csrf is None else {"X-CSRF-Token": csrf}
    response = client.post("/refresh", headers=headers)
    assert response.status_code == 403
    # A sessão continua válida: a tentativa forjada não a derruba.
    assert client.post("/refresh", headers=csrf_header(client, cookie_names)).status_code == 200


def test_csrf_de_outra_sessao_nao_serve(client, cookie_names):
    from fastapi.testclient import TestClient

    from backend.main import app

    register(client, "a@ex.com")
    register(client, "b@ex.com")
    login(client, "a@ex.com")
    with TestClient(app, base_url="https://testserver") as other:
        login(other, "b@ex.com")
        other_csrf = other.cookies.get(cookie_names.csrf)
    assert client.post("/refresh", headers={"X-CSRF-Token": other_csrf}).status_code == 403


def test_refresh_sem_cookie_e_recusado(client):
    response = client.post("/refresh", headers={"X-CSRF-Token": "x"})
    assert response.status_code == 401


def replay(names, refresh_value, csrf_value):
    """Outro cliente (sem o cookie jar da vítima) reapresentando uma cópia."""
    from fastapi.testclient import TestClient

    from backend.main import app

    with TestClient(app, base_url="https://testserver") as attacker:
        return attacker.post(
            "/refresh",
            headers={"X-CSRF-Token": csrf_value, "Cookie": f"{names.refresh}={refresh_value}"},
        )


def test_reuso_de_refresh_fora_da_tolerancia_revoga_a_sessao(client, session, cookie_names, monkeypatch):
    clock = FakeClock(time.time())
    monkeypatch.setattr(deps.token_service_instance, "_clock", clock)
    stolen_refresh = client.cookies.get(cookie_names.refresh)
    stolen_csrf = client.cookies.get(cookie_names.csrf)

    rotated = client.post("/refresh", headers=csrf_header(client, cookie_names))
    assert rotated.status_code == 200
    legit_token = rotated.json()["access_token"]

    clock.advance(settings.REFRESH_REUSE_GRACE_SECONDS + 1)
    assert replay(cookie_names, stolen_refresh, stolen_csrf).status_code == 401
    # Sessão inteira revogada: até o access legítimo emitido na rotação e o
    # refresh atual da vítima.
    assert me(client, legit_token).status_code == 401
    assert me(client, session).status_code == 401
    assert client.post("/refresh", headers=csrf_header(client, cookie_names)).status_code == 401


def test_reuso_dentro_da_tolerancia_nao_derruba_a_sessao(client, session, cookie_names):
    """Duas abas renovando juntas: a segunda recebe 401, mas a sessão segue."""
    first_refresh = client.cookies.get(cookie_names.refresh)
    first_csrf = client.cookies.get(cookie_names.csrf)
    ok = client.post("/refresh", headers=csrf_header(client, cookie_names))
    assert ok.status_code == 200

    assert replay(cookie_names, first_refresh, first_csrf).status_code == 401

    assert me(client, ok.json()["access_token"]).status_code == 200
    assert client.post("/refresh", headers=csrf_header(client, cookie_names)).status_code == 200


def test_sessao_tem_prazo_absoluto(client, session, cookie_names, monkeypatch):
    clock = FakeClock(time.time())
    monkeypatch.setattr(deps.token_service_instance, "_clock", clock)
    clock.advance(settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60 + 1)
    response = client.post("/refresh", headers=csrf_header(client, cookie_names))
    assert response.status_code == 401
    # Cookies apagados na resposta.
    assert any(c.startswith(cookie_names.refresh + '=""') or "max-age=0" in c.lower()
               for c in response.headers.get_list("set-cookie"))


# --- Logout e revogação -------------------------------------------------------


def test_logout_com_bearer_revoga_o_token_e_a_sessao(client, session, cookie_names):
    csrf = csrf_header(client, cookie_names)
    response = client.post("/logout", headers=bearer(session))
    assert response.status_code == 204
    assert me(client, session).status_code == 401  # token revogado
    assert client.post("/refresh", headers=csrf).status_code == 401  # refresh revogado
    assert cookie_names.refresh not in client.cookies


def test_logout_revoga_tokens_anteriores_da_mesma_sessao(client, session, cookie_names):
    renewed = client.post("/refresh", headers=csrf_header(client, cookie_names)).json()["access_token"]
    client.post("/logout", headers=bearer(renewed))
    assert me(client, session).status_code == 401
    assert me(client, renewed).status_code == 401


def test_logout_so_com_cookie_exige_csrf(client, session, cookie_names):
    assert client.post("/logout").status_code == 403
    assert me(client, session).status_code == 200  # nada foi revogado
    assert client.post("/logout", headers=csrf_header(client, cookie_names)).status_code == 204
    assert me(client, session).status_code == 401


def test_logout_nao_afeta_outras_sessoes(client, cookie_names):
    from fastapi.testclient import TestClient

    from backend.main import app

    register(client, "multi@ex.com")
    first = login(client, "multi@ex.com").json()["access_token"]
    with TestClient(app, base_url="https://testserver") as other:
        second = login(other, "multi@ex.com").json()["access_token"]
    client.post("/logout", headers=bearer(first))
    assert me(client, first).status_code == 401
    assert me(client, second).status_code == 200


def test_logout_e_idempotente(client):
    assert client.post("/logout").status_code == 204
    assert client.post("/logout", headers=bearer("token-invalido")).status_code == 204


def test_access_token_nao_passa_do_prazo_da_sessao(client, cookie_names, monkeypatch):
    monkeypatch.setattr(settings, "REFRESH_TOKEN_EXPIRE_MINUTES", settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    register(client, "prazo@ex.com")
    token = login(client, "prazo@ex.com").json()["access_token"]
    claims = jwt.get_unverified_claims(token)
    assert claims["exp"] - claims["iat"] <= settings.REFRESH_TOKEN_EXPIRE_MINUTES * 60


def test_tokens_nao_aparecem_em_logs(client, cookie_names, caplog):
    caplog.set_level(logging.DEBUG)
    register(client, "logs@ex.com")
    token = login(client, "logs@ex.com").json()["access_token"]
    refresh_value = client.cookies.get(cookie_names.refresh)
    csrf = csrf_header(client, cookie_names)
    renewed = client.post("/refresh", headers=csrf).json()["access_token"]
    client.post("/refresh", headers={"X-CSRF-Token": "errado"})
    client.post("/logout", headers=bearer(renewed))
    for secret in (token, renewed, refresh_value, csrf["X-CSRF-Token"], PASSWORD):
        assert secret not in caplog.text


def test_usuario_removido_invalida_a_sessao(client, session, cookie_names):
    deps.user_repository_instance.clear()
    assert me(client, session).status_code == 401
    assert client.post("/refresh", headers=csrf_header(client, cookie_names)).status_code == 401
