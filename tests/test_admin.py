import pytest
from django.contrib.auth import get_user_model

from apps.items.models import Item

from .factories import ItemFactory, UserFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client(client):
    admin = get_user_model().objects.create_superuser(
        username="root",
        name="Root",
        email="root@example.com",
        password="Senha-forte-123",
        matricula="ROOT0001",
    )
    client.force_login(admin)
    return client


def test_admin_lista_itens_excluidos(admin_client):
    item = ItemFactory(title="apagado-visivel", owner=UserFactory())
    item.delete()
    resp = admin_client.get("/admin/items/item/")
    assert resp.status_code == 200
    assert "apagado-visivel" in resp.content.decode()


def test_admin_restaura_item(admin_client):
    item = ItemFactory(owner=UserFactory())
    item.delete()
    resp = admin_client.post(
        "/admin/items/item/",
        {
            "action": "undelete_selected",
            "_selected_action": [item.pk],
            "post": "yes",
        },
    )
    assert resp.status_code in (200, 302)
    assert Item.objects.filter(pk=item.pk).exists()


def test_admin_de_usuarios_abre(admin_client):
    assert admin_client.get("/admin/users/user/").status_code == 200
    assert admin_client.get("/admin/users/user/add/").status_code == 200


def test_admin_escolas_abre(admin_client):
    assert admin_client.get("/admin/escolas/config/").status_code == 200
    assert admin_client.get("/admin/escolas/escola/").status_code == 200
    assert admin_client.get("/admin/escolas/turma/").status_code == 200
