"""SECRET_KEY e validação da configuração (item G)."""

import hashlib
import secrets

import pytest
from pydantic import ValidationError

from backend.core import config
from backend.core.config import Settings, describe_settings_error


def build(**overrides):
    return Settings(_env_file=None, **overrides)


def test_chave_aleatoria_valida_e_aceita():
    key = secrets.token_urlsafe(48)
    assert build(SECRET_KEY=key).SECRET_KEY == key


@pytest.mark.parametrize(
    "key, trecho",
    [
        ("", "não definida"),
        ("   ", "não definida"),
        ("curta-demais-123", "muito curta"),
        ("troque-por-uma-chave-gerada-aleatoriamente-0123", "exemplo ou previsível"),
        ("sua-chave-secreta-muito-longa-e-aleatoria-aqui", "exemplo ou previsível"),
        ("a" * 64, "exemplo ou previsível"),
        ("abababababababababababababababab", "exemplo ou previsível"),
    ],
)
def test_chaves_ausentes_curtas_ou_previsiveis_sao_recusadas(key, trecho):
    with pytest.raises(ValidationError) as error:
        build(SECRET_KEY=key)
    assert trecho in describe_settings_error(error.value)


def test_chave_ja_publicada_e_recusada_pelo_hash(monkeypatch):
    leaked = secrets.token_urlsafe(48)
    monkeypatch.setattr(
        config,
        "_PUBLISHED_SECRET_KEY_HASHES",
        frozenset({hashlib.sha256(leaked.encode()).hexdigest()}),
    )
    with pytest.raises(ValidationError) as error:
        build(SECRET_KEY=leaked)
    assert "já publicada" in describe_settings_error(error.value)


def test_hashes_das_chaves_publicadas_no_repositorio_estao_bloqueados():
    # Os valores não ficam no código; só os hashes das duas chaves que já
    # apareceram no repositório (.env.example antigo e .env do histórico).
    assert len(config._PUBLISHED_SECRET_KEY_HASHES) == 2


def test_mensagem_de_erro_nunca_contem_a_chave():
    key = "segredo-" + secrets.token_hex(4)  # curta: vai falhar
    with pytest.raises(ValidationError) as error:
        build(SECRET_KEY=key)
    assert key not in str(error.value)
    assert key not in describe_settings_error(error.value)


def test_load_settings_falha_com_mensagem_clara(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setattr(Settings, "model_config", {**Settings.model_config, "env_file": None})
    with pytest.raises(RuntimeError) as error:
        config.load_settings()
    assert "SECRET_KEY" in str(error.value)
    assert "secrets.token_urlsafe" in str(error.value)


@pytest.mark.parametrize("algorithm", ["none", "RS256", "HS1"])
def test_algoritmos_fora_da_lista_sao_recusados(algorithm):
    with pytest.raises(ValidationError):
        build(SECRET_KEY=secrets.token_urlsafe(48), ALGORITHM=algorithm)


def test_refresh_nao_pode_ser_menor_que_access():
    with pytest.raises(ValidationError):
        build(SECRET_KEY=secrets.token_urlsafe(48), ACCESS_TOKEN_EXPIRE_MINUTES=60, REFRESH_TOKEN_EXPIRE_MINUTES=30)


def test_env_example_nao_traz_chave_utilizavel():
    from pathlib import Path

    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
    line = next(l for l in example.splitlines() if l.startswith("SECRET_KEY="))
    assert line == "SECRET_KEY="
