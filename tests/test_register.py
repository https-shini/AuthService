"""Cadastro (item D), campo nome (item E) e e-mail duplicado."""

import pytest

from helpers import register


def test_cadastro_responde_201_com_id_email_e_nome(client):
    response = register(client, "ana@ex.com", name="Ana Souza")
    assert response.status_code == 201
    assert response.json() == {"id": 1, "email": "ana@ex.com", "name": "Ana Souza"}


def test_nome_e_opcional_e_volta_null(client):
    response = register(client, "semnome@ex.com")
    assert response.status_code == 201
    assert response.json()["name"] is None


@pytest.mark.parametrize("raw, esperado", [("  Ana   Maria  ", "Ana Maria"), ("   ", None), ("", None), ("José Ñandú", "José Ñandú")])
def test_nome_e_normalizado(client, raw, esperado):
    response = register(client, f"n{abs(hash(raw))}@ex.com", name=raw)
    assert response.status_code == 201
    assert response.json()["name"] == esperado


@pytest.mark.parametrize("raw", ["x" * 101, "Ana\nSouza", "Ana\u0000", "Ana​Souza"])
def test_nome_invalido_e_recusado(client, raw):
    response = register(client, "nome@ex.com", name=raw)
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "name"


def test_email_duplicado_e_recusado_com_400(client):
    assert register(client, "dup@ex.com").status_code == 201
    response = register(client, "dup@ex.com")
    assert response.status_code == 400
    assert response.json() == {"detail": "Email já registrado"}


@pytest.mark.parametrize(
    "senha, mensagem",
    [
        ("abcdefgh", "A senha deve conter pelo menos um número"),
        ("12345678", "A senha deve conter pelo menos uma letra"),
        ("a1", "at least 8 characters"),
        ("a1" + "x" * 71, "no máximo 72 bytes"),
        ("ção1" * 13, "no máximo 72 bytes"),  # 13×6 bytes = 78 bytes, 52 caracteres
    ],
)
def test_regras_de_senha(client, senha, mensagem):
    response = register(client, "senha@ex.com", password=senha)
    assert response.status_code == 422
    assert mensagem in response.json()["detail"][0]["msg"]


def test_senha_de_exatamente_72_bytes_e_aceita(client):
    assert register(client, "limite@ex.com", password="a1" + "x" * 70).status_code == 201


def test_email_invalido_e_recusado(client):
    response = register(client, "nao-e-email")
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"][-1] == "email"


def test_resposta_nao_contem_senha_nem_hash(client):
    body = register(client, "seguro@ex.com").text
    assert "Senha123" not in body and "hashed" not in body and "$2b$" not in body
