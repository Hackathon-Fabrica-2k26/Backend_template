import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.cache import cache

from apps.users.services.otp import _cache_key

from .factories import SENHA

REGISTER = "/api/auth/register/"


@pytest.fixture
def user(db):
    # Os testes de login deste arquivo cobrem o fluxo com OTP; o padrão (sem OTP) fica
    # nos testes de login direto no fim do arquivo.
    from .factories import UserFactory

    return UserFactory(email="ana@example.com", name="Ana", otp_ativo=True)


@pytest.mark.django_db
def test_registro_ok(api_client):
    resp = api_client.post(
        REGISTER,
        {
            "matricula": "20260001",
            "email": "bia@example.com",
            "name": "Bia",
            "password": SENHA,
        },
    )
    assert resp.status_code == 201
    assert "password" not in resp.json()

    usuario = get_user_model().objects.get(email="bia@example.com")
    assert usuario.check_password(SENHA)
    assert usuario.matricula == "20260001"


@pytest.mark.django_db
def test_registro_aceita_ano_opcional(api_client):
    resp = api_client.post(
        REGISTER,
        {
            "matricula": "20260099",
            "email": "bia-ano@example.com",
            "name": "Bia",
            "password": SENHA,
            "ano": "5º ano",
        },
    )

    assert resp.status_code == 201
    assert get_user_model().objects.get(email="bia-ano@example.com").ano == "5º ano"


@pytest.mark.django_db
def test_registro_email_repetido_sem_diferenciar_maiusculas(api_client, user):
    resp = api_client.post(
        REGISTER,
        {
            "matricula": "20260002",
            "email": "ANA@example.com",
            "name": "Outra",
            "password": SENHA,
        },
    )
    assert resp.status_code == 400
    assert "email" in resp.json()


@pytest.mark.django_db
def test_registro_email_obrigatorio(api_client):
    resp = api_client.post(
        REGISTER,
        {
            "matricula": "20260003",
            "name": "Dani",
            "password": SENHA,
        },
    )
    assert resp.status_code == 400
    assert "email" in resp.json()


@pytest.mark.django_db
def test_registro_senha_fraca(api_client):
    resp = api_client.post(
        REGISTER,
        {
            "matricula": "20260004",
            "email": "c@example.com",
            "name": "Cris",
            "password": "123",
        },
    )
    assert resp.status_code == 400
    assert "password" in resp.json()


@pytest.mark.django_db
def test_registro_senha_parecida_com_email(api_client):
    resp = api_client.post(
        REGISTER,
        {
            "matricula": "20260005",
            "email": "carlosmendes@example.com",
            "name": "Carlos",
            "password": "carlosmendes1",
        },
    )
    assert resp.status_code == 400
    assert "password" in resp.json()


@pytest.mark.django_db
def test_registro_tem_limite_de_requisicoes(api_client):
    codigos = [
        api_client.post(
            REGISTER,
            {
                "matricula": f"2026{i:04d}",
                "email": f"u{i}@example.com",
                "name": f"U{i}",
                "password": SENHA,
            },
        ).status_code
        for i in range(12)
    ]

    assert codigos[:10] == [201] * 10
    assert 429 in codigos[10:]


@pytest.mark.django_db
def test_login_por_matricula(api_client, user):
    resp = api_client.post(
        "/api/auth/login/",
        {"matricula": user.matricula, "password": SENHA},
    )

    assert resp.status_code == 200

    dados = resp.json()
    assert "otp_token" in dados
    assert "email" in dados
    assert "access" not in dados
    assert "refresh" not in dados


@pytest.mark.django_db
def test_me_sem_token(api_client):
    assert api_client.get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_create_superuser_exige_email():
    with pytest.raises(ValueError):
        get_user_model().objects.create_superuser("", "x")


@pytest.mark.django_db
def test_usuario_usa_matricula_como_username():
    assert get_user_model().USERNAME_FIELD == "matricula"


@pytest.mark.django_db
def test_login_com_senha_errada_retorna_401(api_client, user):
    resp = api_client.post(
        "/api/auth/login/",
        {"matricula": user.matricula, "password": "senha-errada"},
    )

    assert resp.status_code == 401
    assert "otp_token" not in resp.json()
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_otp_codigo_errado_retorna_400(api_client, user):
    login = api_client.post(
        "/api/auth/login/",
        {"matricula": user.matricula, "password": SENHA},
    )

    assert login.status_code == 200

    resp = api_client.post(
        "/api/auth/otp/verify/",
        {
            "otp_token": login.json()["otp_token"],
            "code": "99999",
        },
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_otp_codigo_correto_retorna_tokens(api_client, user):
    login = api_client.post(
        "/api/auth/login/",
        {"matricula": user.matricula, "password": SENHA},
    )

    assert login.status_code == 200

    codigo = mail.outbox[-1].subject.split(" ", 1)[0]

    resp = api_client.post(
        "/api/auth/otp/verify/",
        {
            "otp_token": login.json()["otp_token"],
            "code": codigo,
        },
    )

    assert resp.status_code == 200
    assert resp.json()["access"]
    assert resp.json()["refresh"]

    repeticao = api_client.post(
        "/api/auth/otp/verify/",
        {
            "otp_token": login.json()["otp_token"],
            "code": codigo,
        },
    )

    assert repeticao.status_code == 400


@pytest.mark.django_db
def test_otp_expirado_retorna_400(api_client, user):
    login = api_client.post(
        "/api/auth/login/",
        {"matricula": user.matricula, "password": SENHA},
    )

    assert login.status_code == 200

    otp_token = login.json()["otp_token"]
    cache.delete(_cache_key(otp_token))

    resp = api_client.post(
        "/api/auth/otp/verify/",
        {
            "otp_token": otp_token,
            "code": "1234",
        },
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_otp_atinge_limite_de_tentativas(api_client, user):
    login = api_client.post(
        "/api/auth/login/",
        {"matricula": user.matricula, "password": SENHA},
    )

    assert login.status_code == 200

    otp_token = login.json()["otp_token"]

    for _ in range(5):
        resp = api_client.post(
            "/api/auth/otp/verify/",
            {
                "otp_token": otp_token,
                "code": "99999",
            },
        )

    assert resp.status_code == 400

    chave = _cache_key(otp_token)
    assert cache.get(chave) is None


@pytest.mark.django_db
def test_reenvio_otp_respeita_intervalo(api_client, user):
    login = api_client.post(
        "/api/auth/login/",
        {"matricula": user.matricula, "password": SENHA},
    )

    assert login.status_code == 200

    otp_token = login.json()["otp_token"]

    resp = api_client.post(
        "/api/auth/otp/resend/",
        {"otp_token": otp_token},
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_editar_perfil_usuario(api_client, user):
    api_client.force_authenticate(user=user)
    resp = api_client.patch(
        "/api/auth/me/",
        {"name": "Professora Atualizada", "email": "atualizada@escola.com"},
    )
    assert resp.status_code == 200
    user.refresh_from_db()
    assert user.name == "Professora Atualizada"
    assert user.email == "atualizada@escola.com"


def test_email_otp_tem_html_com_digitos_e_logo_embutida(api_client, user):
    api_client.post("/api/auth/login/", {"matricula": user.matricula, "password": SENHA})

    email = mail.outbox[-1]
    codigo = email.subject.split(" ", 1)[0]
    assert codigo.isdigit()
    assert codigo in email.body
    html, tipo = email.alternatives[0]
    assert tipo == "text/html"
    assert "cid:logo-marsupi" in html
    for digito in codigo:
        assert f">{digito}</td>" in html
    anexos = email.message().get_payload()
    assert any(parte.get("Content-ID") == "<logo-marsupi>" for parte in anexos)


def test_otp_vem_desligado_por_padrao(db):
    from .factories import UserFactory

    assert UserFactory().otp_ativo is False


def test_login_sem_otp_entra_direto_com_tokens(api_client, db):
    from .factories import UserFactory

    professora = UserFactory()
    resp = api_client.post(
        "/api/auth/login/", {"matricula": professora.matricula, "password": SENHA}
    )

    assert resp.status_code == 200
    dados = resp.json()
    assert dados["otp_required"] is False
    assert dados["access"] and dados["refresh"]
    assert "otp_token" not in dados
    assert len(mail.outbox) == 0

    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {dados['access']}")
    assert api_client.get("/api/auth/me/").json()["otp_ativo"] is False


def test_login_com_otp_ativo_exige_codigo(api_client, user):
    resp = api_client.post("/api/auth/login/", {"matricula": user.matricula, "password": SENHA})

    dados = resp.json()
    assert dados["otp_required"] is True
    assert "otp_token" in dados
    assert "access" not in dados
    assert len(mail.outbox) == 1


def test_professora_liga_e_desliga_otp_no_perfil(api_client, db):
    from .factories import UserFactory

    professora = UserFactory()
    api_client.force_authenticate(user=professora)

    assert api_client.patch("/api/auth/me/", {"otp_ativo": True}).json()["otp_ativo"] is True
    professora.refresh_from_db()
    assert professora.otp_ativo is True

    api_client.patch("/api/auth/me/", {"otp_ativo": False})
    professora.refresh_from_db()
    assert professora.otp_ativo is False
