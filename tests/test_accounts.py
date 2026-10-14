import pytest

REGISTER = "/api/auth/register/"


@pytest.mark.django_db
def test_registro_ok(api_client):
    resp = api_client.post(
        REGISTER,
        {"username": "bia", "email": "bia@example.com", "password": "Senha-forte-123"},
    )
    assert resp.status_code == 201
    assert "password" not in resp.json()


@pytest.mark.django_db
def test_registro_username_repetido(api_client, user):
    resp = api_client.post(
        REGISTER, {"username": "ana", "email": "x@example.com", "password": "Senha-forte-123"}
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_registro_senha_fraca(api_client):
    resp = api_client.post(
        REGISTER, {"username": "cris", "email": "c@example.com", "password": "123"}
    )
    assert resp.status_code == 400


def test_login_e_me(api_client, user):
    resp = api_client.post("/api/auth/login/", {"username": "ana", "password": "Senha-forte-123"})
    assert resp.status_code == 200
    token = resp.json()["access"]
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    me = api_client.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["username"] == "ana"


@pytest.mark.django_db
def test_me_sem_token(api_client):
    assert api_client.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_registro_email_repetido(api_client, user):
    resp = api_client.post(
        REGISTER, {"username": "outra", "email": "ANA@example.com", "password": "Senha-forte-123"}
    )
    assert resp.status_code == 400
    assert "email" in resp.json()


@pytest.mark.django_db
def test_registro_email_obrigatorio(api_client):
    resp = api_client.post(REGISTER, {"username": "dani", "password": "Senha-forte-123"})
    assert resp.status_code == 400
    assert "email" in resp.json()


@pytest.mark.django_db
def test_registro_senha_parecida_com_username(api_client):
    resp = api_client.post(
        REGISTER,
        {"username": "carlosmendes", "email": "c@example.com", "password": "carlosmendes1"},
    )
    assert resp.status_code == 400
    assert "password" in resp.json()


@pytest.mark.django_db
def test_registro_tem_limite_de_requisicoes(api_client):
    codigos = [
        api_client.post(
            REGISTER,
            {"username": f"u{i}", "email": f"u{i}@example.com", "password": "Senha-forte-123"},
        ).status_code
        for i in range(12)
    ]
    assert codigos[:10] == [201] * 10
    assert 429 in codigos[10:]
