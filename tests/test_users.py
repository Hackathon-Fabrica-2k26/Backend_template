import pytest
from django.contrib.auth import get_user_model

from .factories import SENHA, UserFactory

REGISTER = "/api/auth/register/"


@pytest.mark.django_db
def test_registro_ok(api_client):
    resp = api_client.post(REGISTER, {"email": "bia@example.com", "name": "Bia", "password": SENHA})
    assert resp.status_code == 201
    assert "password" not in resp.json()
    assert get_user_model().objects.get(email="bia@example.com").check_password(SENHA)


@pytest.mark.django_db
def test_registro_email_repetido_sem_diferenciar_maiusculas(api_client, user):
    resp = api_client.post(
        REGISTER, {"email": "ANA@example.com", "name": "Outra", "password": SENHA}
    )
    assert resp.status_code == 400
    assert "email" in resp.json()


@pytest.mark.django_db
def test_registro_email_obrigatorio(api_client):
    resp = api_client.post(REGISTER, {"name": "Dani", "password": SENHA})
    assert resp.status_code == 400
    assert "email" in resp.json()


@pytest.mark.django_db
def test_registro_senha_fraca(api_client):
    resp = api_client.post(REGISTER, {"email": "c@example.com", "name": "Cris", "password": "123"})
    assert resp.status_code == 400


@pytest.mark.django_db
def test_registro_senha_parecida_com_email(api_client):
    resp = api_client.post(
        REGISTER,
        {"email": "carlosmendes@example.com", "name": "Carlos", "password": "carlosmendes1"},
    )
    assert resp.status_code == 400
    assert "password" in resp.json()


@pytest.mark.django_db
def test_registro_tem_limite_de_requisicoes(api_client):
    codigos = [
        api_client.post(
            REGISTER, {"email": f"u{i}@example.com", "name": f"U{i}", "password": SENHA}
        ).status_code
        for i in range(12)
    ]
    assert codigos[:10] == [201] * 10
    assert 429 in codigos[10:]


def test_login_por_email_e_me(api_client, user):
    resp = api_client.post("/api/auth/login/", {"email": "ana@example.com", "password": SENHA})
    assert resp.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {resp.json()['access']}")
    me = api_client.get("/api/auth/me/")
    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"


@pytest.mark.django_db
def test_me_sem_token(api_client):
    assert api_client.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_create_superuser_exige_email():
    with pytest.raises(ValueError):
        get_user_model().objects.create_superuser("", "x")


@pytest.mark.django_db
def test_usuario_nao_tem_username():
    assert UserFactory().USERNAME_FIELD == "email"
