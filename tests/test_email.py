"""Normalização de e-mail (item B) e compatibilidade com usuários antigos."""

import pytest

from backend.core.security import get_password_hash
from backend.dependencies import dependencies as deps
from backend.models.user import User
from helpers import PASSWORD, bearer, login, register


def legacy_user(email, name=None):
    """Usuário gravado ANTES da normalização (parte local com maiúsculas)."""
    return deps.user_repository_instance.save(
        User(id=None, email=email, hashed_password=get_password_hash(PASSWORD), name=name)
    )


@pytest.mark.parametrize("typed", ["Ana.Souza@Ex.COM", "ANA.SOUZA@EX.COM", "ana.souza@ex.com", "  aNa.SoUzA@ex.com  "])
def test_cadastro_normaliza_para_minusculas(client, typed):
    response = register(client, typed)
    assert response.status_code == 201
    assert response.json()["email"] == "ana.souza@ex.com"


@pytest.mark.parametrize("typed", ["ana@ex.com", "ANA@EX.COM", "Ana@Ex.Com", "aNA@ex.COM", " ana@ex.com "])
def test_login_aceita_qualquer_combinacao_de_maiusculas(client, typed):
    register(client, "Ana@Ex.com")
    response = login(client, typed)
    assert response.status_code == 200, typed
    me = client.get("/me", headers=bearer(response.json()["access_token"]))
    assert me.json()["email"] == "ana@ex.com"


@pytest.mark.parametrize("second", ["ANA@ex.com", "ana@EX.COM", "Ana@Ex.Com"])
def test_cadastro_duplicado_ignora_maiusculas(client, second):
    assert register(client, "ana@ex.com").status_code == 201
    response = register(client, second)
    assert response.status_code == 400
    assert response.json()["detail"] == "Email já registrado"
    assert len(deps.user_repository_instance.get_all()) == 1


def test_senha_errada_continua_recusada_em_qualquer_caixa(client):
    register(client, "ana@ex.com")
    assert login(client, "ANA@EX.COM", password="Errada999").status_code == 401


# --- Compatibilidade com usuários antigos ---------------------------------


@pytest.mark.parametrize("typed", ["Caso@ex.com", "caso@ex.com", "CASO@EX.COM", "caso@EX.com"])
def test_usuario_antigo_com_maiusculas_entra_com_qualquer_variacao(client, typed):
    legacy_user("Caso@ex.com")
    response = login(client, typed)
    assert response.status_code == 200, typed
    me = client.get("/me", headers=bearer(response.json()["access_token"]))
    # O e-mail guardado não é reescrito (nenhuma migração destrutiva).
    assert me.json() == {"id": 1, "email": "Caso@ex.com", "name": None}


def test_usuario_antigo_impede_cadastro_duplicado_em_minusculas(client):
    legacy_user("Caso@ex.com")
    assert register(client, "caso@ex.com").status_code == 400


def test_dois_usuarios_antigos_que_so_diferem_na_caixa(client):
    """Duplicatas criadas antes da regra: cada uma entra com a forma exata.
    Outra variação vai para a conta cuja forma salva já é a normalizada
    (passo 2 de find_for_login) — a senha dela continua sendo exigida."""
    first = legacy_user("Dup@ex.com")
    second = legacy_user("dup@ex.com")

    token_first = login(client, "Dup@ex.com").json()["access_token"]
    token_second = login(client, "dup@ex.com").json()["access_token"]
    assert client.get("/me", headers=bearer(token_first)).json()["id"] == first.id
    assert client.get("/me", headers=bearer(token_second)).json()["id"] == second.id

    variant = login(client, "DUP@ex.com")
    assert variant.status_code == 200
    assert client.get("/me", headers=bearer(variant.json()["access_token"])).json()["id"] == second.id


def test_duplicatas_antigas_sem_forma_normalizada_sao_ambiguas(client):
    """Nenhuma das duplicatas está em minúsculas: escolher uma seria palpite,
    então a variação é recusada (401 genérico); as formas exatas entram."""
    legacy_user("Amb@ex.com")
    legacy_user("aMB@ex.com")
    assert login(client, "Amb@ex.com").status_code == 200
    assert login(client, "aMB@ex.com").status_code == 200
    ambiguous = login(client, "amb@ex.com")
    assert ambiguous.status_code == 401
    assert ambiguous.json()["detail"] == "Email ou senha incorretos"


def test_usuario_antigo_sem_nome_continua_funcionando(client):
    legacy_user("antigo@ex.com")
    token = login(client, "antigo@ex.com").json()["access_token"]
    assert client.get("/me", headers=bearer(token)).json()["name"] is None


def test_email_inexistente_e_senha_errada_tem_a_mesma_resposta(client):
    register(client, "existe@ex.com")
    unknown = login(client, "naoexiste@ex.com")
    wrong = login(client, "existe@ex.com", password="Errada999")
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()
