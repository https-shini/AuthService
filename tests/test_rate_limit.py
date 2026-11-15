"""Rate limiting do POST /token (item A)."""

import logging

import pytest

from backend.core.config import settings
from backend.core.rate_limit import LoginLimits, LoginRateLimiter
from backend.dependencies import dependencies as deps
from helpers import PASSWORD, FakeClock, login, register

WRONG = "Errada999"


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock(1_000.0)
    monkeypatch.setattr(deps.login_rate_limiter_instance, "_clock", fake)
    return fake


def fail(client, email, times, headers=None):
    return [login(client, email, WRONG, headers=headers).status_code for _ in range(times)]


def test_bloqueia_apos_5_falhas_do_mesmo_ip_para_a_conta(client, clock):
    register(client, "alvo@ex.com")
    assert fail(client, "alvo@ex.com", 5) == [401] * 5

    blocked = login(client, "alvo@ex.com", WRONG)
    assert blocked.status_code == 429
    retry = int(blocked.headers["Retry-After"])
    assert 0 < retry <= settings.LOGIN_LOCKOUT_SECONDS
    assert f"{retry} s" in blocked.json()["detail"]


def test_durante_o_bloqueio_nem_a_senha_correta_e_testada(client, clock):
    register(client, "alvo@ex.com")
    fail(client, "alvo@ex.com", 5)
    # Sem oráculo: a senha certa também recebe 429 enquanto durar o bloqueio.
    assert login(client, "alvo@ex.com", PASSWORD).status_code == 429


def test_trocar_maiusculas_nao_contorna_o_limite(client, clock):
    register(client, "alvo@ex.com")
    for variant in ["alvo@ex.com", "ALVO@ex.com", "Alvo@Ex.com", "aLvO@EX.COM", "ALVO@EX.COM"]:
        assert login(client, variant, WRONG).status_code == 401
    assert login(client, "AlVo@eX.cOm", WRONG).status_code == 429


def test_bloqueio_expira_e_o_login_volta_a_funcionar(client, clock):
    register(client, "alvo@ex.com")
    fail(client, "alvo@ex.com", 5)
    assert login(client, "alvo@ex.com", PASSWORD).status_code == 429

    clock.advance(settings.LOGIN_LOCKOUT_SECONDS - 1)
    assert login(client, "alvo@ex.com", PASSWORD).status_code == 429
    clock.advance(2)
    assert login(client, "alvo@ex.com", PASSWORD).status_code == 200


def test_login_certo_zera_as_falhas_daquele_ip(client, clock):
    register(client, "alvo@ex.com")
    fail(client, "alvo@ex.com", 4)
    assert login(client, "alvo@ex.com", PASSWORD).status_code == 200
    # Contador do par IP+conta zerado: mais 4 falhas ainda não bloqueiam.
    assert fail(client, "alvo@ex.com", 4) == [401] * 4


def test_falhas_antigas_saem_da_janela(client, clock):
    register(client, "alvo@ex.com")
    fail(client, "alvo@ex.com", 4)
    clock.advance(settings.LOGIN_FAILURE_WINDOW_SECONDS + 1)
    assert fail(client, "alvo@ex.com", 4) == [401] * 4


def test_limite_por_ip_freia_varredura_de_contas(client, clock, monkeypatch):
    monkeypatch.setattr(
        deps.login_rate_limiter_instance,
        "limits",
        LoginLimits(ip_max_attempts=6, ip_window=60, account_ip_max_failures=5,
                    account_max_failures=20, failure_window=900, lockout=900),
    )
    statuses = [login(client, f"conta{i}@ex.com", WRONG).status_code for i in range(7)]
    assert statuses == [401] * 6 + [429]
    clock.advance(61)
    assert login(client, "conta99@ex.com", WRONG).status_code == 401


def test_x_forwarded_for_e_ignorado_sem_proxy_configurado(client, clock):
    """Com TRUSTED_PROXY_HOPS=0, trocar o header não gera IPs novos."""
    register(client, "alvo@ex.com")
    for i in range(5):
        login(client, "alvo@ex.com", WRONG, headers={"X-Forwarded-For": f"10.0.0.{i}"})
    assert login(client, "alvo@ex.com", WRONG, headers={"X-Forwarded-For": "10.9.9.9"}).status_code == 429


def test_com_proxy_confiavel_usa_o_ip_acrescentado_pelo_proxy(client, clock, monkeypatch):
    """O cliente pode forjar o INÍCIO da lista; vale o último item (do proxy)."""
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    register(client, "alvo@ex.com")
    for i in range(5):
        spoofed = {"X-Forwarded-For": f"1.1.1.{i}, 203.0.113.7"}
        assert login(client, "alvo@ex.com", WRONG, headers=spoofed).status_code == 401
    assert login(client, "alvo@ex.com", WRONG, headers={"X-Forwarded-For": "9.9.9.9, 203.0.113.7"}).status_code == 429
    # Outro cliente real (outro IP acrescentado pelo proxy) não é afetado pelo par IP+conta.
    assert login(client, "alvo@ex.com", PASSWORD, headers={"X-Forwarded-For": "198.51.100.4"}).status_code == 200


def test_ataque_distribuido_bloqueia_a_conta(client, clock, monkeypatch):
    monkeypatch.setattr(settings, "TRUSTED_PROXY_HOPS", 1)
    register(client, "alvo@ex.com")
    limit = settings.LOGIN_ACCOUNT_MAX_FAILURES
    for i in range(limit):
        headers = {"X-Forwarded-For": f"198.51.100.{i}"}  # 4 falhas por IP: nenhum par bloqueia
        assert login(client, "alvo@ex.com", WRONG, headers=headers).status_code == 401
    assert login(client, "alvo@ex.com", PASSWORD, headers={"X-Forwarded-For": "192.0.2.200"}).status_code == 429


def test_senha_e_token_nunca_aparecem_nos_logs(client, clock, caplog):
    caplog.set_level(logging.DEBUG)
    register(client, "log@ex.com")
    fail(client, "log@ex.com", 6)
    token = login(client, "log@ex.com", PASSWORD)
    text = caplog.text
    assert WRONG not in text and PASSWORD not in text
    assert "Login bloqueado" in text
    if token.status_code == 200:
        assert token.json()["access_token"] not in text


def test_limitador_descarta_estado_antigo():
    fake = FakeClock(0.0)
    limiter = LoginRateLimiter(LoginLimits(5, 60, 5, 20, 900, 900), clock=fake)
    for i in range(10):
        limiter.record_attempt(f"10.0.0.{i}")
        limiter.record_failure(f"10.0.0.{i}", "x@ex.com")
    fake.advance(10_000)
    limiter._prune(fake())
    assert not limiter._attempts_by_ip and not limiter._failures and not limiter._locked_until
