import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.escolas.models import Config

from .factories import ConfigFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    admin = get_user_model().objects.create_superuser(
        matricula="ADMIN001", email="admin@example.com", password="Senha@forte123", name="Admin"
    )
    client.force_login(admin)
    return client


def _dados(config, **extra):
    return {"modelo": config.modelo, "campos_form": "{}", "api_key": "", **extra}


def test_tela_de_edicao_nao_exibe_a_chave(admin_client):
    config = ConfigFactory(api_key="chave-secreta-123")
    url = reverse("admin:escolas_config_change", args=[config.pk])

    resp = admin_client.get(url)

    assert resp.status_code == 200
    assert "chave-secreta-123" not in resp.content.decode()


def test_salvar_sem_chave_mantem_a_atual(admin_client):
    config = ConfigFactory(api_key="chave-antiga")
    url = reverse("admin:escolas_config_change", args=[config.pk])

    resp = admin_client.post(url, _dados(config, modelo="gemini-novo"))

    assert resp.status_code == 302
    config.refresh_from_db()
    assert config.api_key == "chave-antiga"
    assert config.modelo == "gemini-novo"


def test_salvar_com_chave_troca_a_chave(admin_client):
    config = ConfigFactory(api_key="chave-antiga")
    url = reverse("admin:escolas_config_change", args=[config.pk])

    resp = admin_client.post(url, _dados(config, api_key="  chave-nova  "))

    assert resp.status_code == 302
    config.refresh_from_db()
    assert config.api_key == "chave-nova"


def test_criar_config_pelo_admin_grava_a_chave(admin_client):
    url = reverse("admin:escolas_config_add")

    resp = admin_client.post(
        url, {"modelo": "gemini", "campos_form": "{}", "api_key": "chave-criada"}
    )

    assert resp.status_code == 302
    assert Config.objects.get(modelo="gemini").api_key == "chave-criada"
