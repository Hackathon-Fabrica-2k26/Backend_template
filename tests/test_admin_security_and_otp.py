import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework import status

from .factories import SENHA, UserFactory

pytestmark = pytest.mark.django_db
User = get_user_model()


def test_staff_sem_otp_ativo_tem_otp_obrigatorio_no_login_api(api_client):
    staff_user = UserFactory(is_staff=True, otp_ativo=False)

    resp = api_client.post(
        "/api/auth/login/",
        {"matricula": staff_user.matricula, "password": SENHA},
    )

    assert resp.status_code == status.HTTP_200_OK
    dados = resp.json()
    assert dados["otp_required"] is True
    assert "otp_token" in dados
    assert "access" not in dados
    assert len(mail.outbox) == 1


def test_superuser_sem_otp_ativo_tem_otp_obrigatorio_no_login_api(api_client):
    super_user = UserFactory(is_superuser=True, is_staff=True, otp_ativo=False)

    resp = api_client.post(
        "/api/auth/login/",
        {"matricula": super_user.matricula, "password": SENHA},
    )

    assert resp.status_code == status.HTTP_200_OK
    dados = resp.json()
    assert dados["otp_required"] is True
    assert "otp_token" in dados
    assert len(mail.outbox) == 1


def test_usuario_comum_sem_otp_entra_direto(api_client):
    comum = UserFactory(is_staff=False, is_superuser=False, otp_ativo=False)

    resp = api_client.post(
        "/api/auth/login/",
        {"matricula": comum.matricula, "password": SENHA},
    )

    assert resp.status_code == status.HTTP_200_OK
    dados = resp.json()
    assert dados["otp_required"] is False
    assert dados["access"] and dados["refresh"]
    assert len(mail.outbox) == 0


def test_admin_login_exige_otp_para_staff(client):
    staff = User.objects.create_user(
        matricula="STAFF01",
        email="staff@example.com",
        password="SenhaForte@123",
        name="Staff",
        is_staff=True,
        otp_ativo=False,
    )
    url_login = reverse("admin:login")

    # 1. Envio de usuário e senha corretos sem OTP dispara o envio de e-mail e pede o código
    resp_passo1 = client.post(
        url_login,
        {"username": staff.matricula, "password": "SenhaForte@123"},
    )
    assert resp_passo1.status_code == 200
    assert len(mail.outbox) == 1
    assert "Código de verificação enviado para o seu e-mail" in resp_passo1.content.decode()

    # 2. Envio com código OTP incorreto é rejeitado
    resp_erro_otp = client.post(
        url_login,
        {"username": staff.matricula, "password": "SenhaForte@123", "otp_code": "9999"},
    )
    assert resp_erro_otp.status_code == 200
    assert "Código de verificação incorreto" in resp_erro_otp.content.decode()

    # 3. Extrai o código de 4 dígitos enviado no e-mail e conclui o login
    import re

    match = re.search(r"\b(\d{4})\b", mail.outbox[0].body)
    assert match is not None
    codigo_correto = match.group(1)

    resp_sucesso = client.post(
        url_login,
        {"username": staff.matricula, "password": "SenhaForte@123", "otp_code": codigo_correto},
        follow=True,
    )
    assert resp_sucesso.status_code == 200
    assert resp_sucesso.context["user"].is_authenticated
    assert resp_sucesso.context["user"].pk == staff.pk


def test_admin_login_bloqueia_apos_5_tentativas_com_axes(client):
    url_login = reverse("admin:login")
    matricula_alvo = "ADMIN_BRUTE_FORCE"

    # Realiza 5 tentativas incorretas
    for _ in range(5):
        resp = client.post(
            url_login,
            {"username": matricula_alvo, "password": "senha-errada"},
        )
        assert resp.status_code == 200

    # A 6ª tentativa deve ser bloqueada pelo django-axes (403 Forbidden)
    resp_bloqueado = client.post(
        url_login,
        {"username": matricula_alvo, "password": "senha-errada"},
    )
    assert resp_bloqueado.status_code == 403


def test_docs_e_schema_em_producao_exigem_login(client, auth_client, settings):
    settings.DEBUG = False
    settings.SPECTACULAR_SETTINGS = {
        **settings.SPECTACULAR_SETTINGS,
        "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAuthenticated"],
    }

    # Sem autenticação em produção: bloqueado (401 ou 403)
    resp_docs = client.get("/api/docs/")
    assert resp_docs.status_code in (401, 403)

    resp_schema = client.get("/api/schema/")
    assert resp_schema.status_code in (401, 403)

    # Com autenticação: liberado (200)
    resp_docs_auth = auth_client.get("/api/docs/")
    assert resp_docs_auth.status_code == 200

    resp_schema_auth = auth_client.get("/api/schema/")
    assert resp_schema_auth.status_code == 200


def test_docs_e_schema_em_desenvolvimento_sao_publicos(client, settings):
    settings.DEBUG = True
    settings.SPECTACULAR_SETTINGS = {
        **settings.SPECTACULAR_SETTINGS,
        "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"],
    }

    assert client.get("/api/docs/").status_code == 200
    assert client.get("/api/schema/").status_code == 200
