import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from rest_framework import status

from .factories import SENHA, UserFactory

pytestmark = pytest.mark.django_db
User = get_user_model()


def test_staff_sem_otp_ativo_tem_otp_obrigatorio_no_login_api(api_client):
    staff_user = UserFactory(otp_ativo=False)
    staff_user.is_staff = True
    staff_user.save(update_fields=["is_staff"])

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
    super_user = User.objects.create_superuser(
        matricula="SUPER01",
        email="super@example.com",
        password=SENHA,
        name="Super",
    )
    super_user.otp_ativo = False
    super_user.save(update_fields=["otp_ativo"])

    resp = api_client.post(
        "/api/auth/login/",
        {"matricula": super_user.matricula, "password": SENHA},
    )

    assert resp.status_code == status.HTTP_200_OK
    dados = resp.json()
    assert dados["otp_required"] is True
    assert "otp_token" in dados
    assert "access" not in dados
    assert len(mail.outbox) == 1


def test_usuario_comum_sem_otp_entra_direto(api_client):
    comum = UserFactory(otp_ativo=False)

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
    staff = User.objects.create_superuser(
        matricula="STAFF01",
        email="staff@example.com",
        password="SenhaForte@123",
        name="Staff",
    )
    staff.otp_ativo = False
    staff.save(update_fields=["otp_ativo"])

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
    assert "Código incorreto" in resp_erro_otp.content.decode()

    # 3. Extrai o código de 4 dígitos enviado no e-mail e conclui o login
    match = re.search(r"\b(\d{4})\b", mail.outbox[0].body)
    assert match is not None
    codigo_correto = match.group(1)

    resp_sucesso = client.post(
        url_login,
        {"username": staff.matricula, "password": "SenhaForte@123", "otp_code": codigo_correto},
    )
    assert resp_sucesso.status_code == 302
    assert client.session["_auth_user_id"] == str(staff.pk)

    # Verifica que usuário logado acessa a home do admin
    resp_admin = client.get(reverse("admin:index"))
    assert resp_admin.status_code == 200
    assert resp_admin.context["user"].is_authenticated
    assert resp_admin.context["user"].pk == staff.pk


def test_admin_login_bloqueia_apos_5_tentativas_com_axes(client):
    from axes.utils import reset

    reset()
    try:
        url_login = reverse("admin:login")
        matricula_alvo = "ADMIN_BRUTE_FORCE"

        # Realiza tentativas incorretas até acionar o bloqueio
        for _ in range(4):
            resp = client.post(
                url_login,
                {"username": matricula_alvo, "password": "senha-errada"},
            )
            assert resp.status_code == 200

        # A partir da 5ª tentativa é bloqueado pelo django-axes (403 ou 429)
        resp_bloqueado = client.post(
            url_login,
            {"username": matricula_alvo, "password": "senha-errada"},
        )
        assert resp_bloqueado.status_code in (403, 429)
    finally:
        reset()


def test_spectacular_serve_permissions_producao_vs_dev(monkeypatch):
    from tests.test_settings import recarregar

    cfg_prod = recarregar(monkeypatch, SECRET_KEY="x", DEBUG="False")
    assert cfg_prod.SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] == [
        "rest_framework.permissions.IsAuthenticated"
    ]

    cfg_dev = recarregar(monkeypatch, SECRET_KEY="x", DEBUG="True")
    assert cfg_dev.SPECTACULAR_SETTINGS["SERVE_PERMISSIONS"] == [
        "rest_framework.permissions.AllowAny"
    ]


def test_docs_e_schema_em_producao_exigem_login(rf):
    from django.contrib.auth.models import AnonymousUser
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
    from rest_framework.permissions import IsAuthenticated

    view_docs = SpectacularSwaggerView.as_view(permission_classes=[IsAuthenticated])
    view_schema = SpectacularAPIView.as_view(permission_classes=[IsAuthenticated])

    req_anon = rf.get("/api/docs/")
    req_anon.user = AnonymousUser()

    resp_docs = view_docs(req_anon)
    assert resp_docs.status_code in (401, 403)

    resp_schema = view_schema(req_anon)
    assert resp_schema.status_code in (401, 403)


def test_docs_e_schema_em_desenvolvimento_sao_publicos(client):
    assert client.get("/api/docs/").status_code == 200
    assert client.get("/api/schema/").status_code == 200
