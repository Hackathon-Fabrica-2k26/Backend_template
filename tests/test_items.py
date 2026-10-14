import pytest

from apps.items.models import Item

from .factories import ItemFactory, UserFactory

URL = "/api/items/"


@pytest.mark.django_db
def test_sem_token(api_client):
    assert api_client.get(URL).status_code == 401


def test_criar_e_listar(auth_client, user):
    resp = auth_client.post(URL, {"title": "Primeiro", "description": "teste"})
    assert resp.status_code == 201
    assert resp.json()["owner"] == user.id
    lista = auth_client.get(URL).json()
    assert lista["count"] == 1


def test_filtro_done(auth_client, user):
    ItemFactory(title="a", owner=user, done=True)
    ItemFactory(title="b", owner=user, done=False)
    resp = auth_client.get(URL, {"done": "true"}).json()
    assert [i["title"] for i in resp["results"]] == ["a"]


def test_item_de_outro_usuario_404(auth_client, db):
    item = ItemFactory(title="secreto", owner=UserFactory())
    assert auth_client.get(f"{URL}{item.id}/").status_code == 404


def test_delete_e_logico(auth_client, user):
    item = ItemFactory(owner=user)
    assert auth_client.delete(f"{URL}{item.id}/").status_code == 204
    assert auth_client.get(f"{URL}{item.id}/").status_code == 404
    assert Item.all_objects.filter(pk=item.pk).exists()


def test_titulo_obrigatorio(auth_client):
    assert auth_client.post(URL, {"description": "sem título"}).status_code == 400


def test_falha_no_broker_nao_quebra_envio(monkeypatch):
    from apps.items import tasks

    def quebra(*args, **kwargs):
        raise RuntimeError("broker fora do ar")

    monkeypatch.setattr(tasks.notificar_item_criado, "delay", quebra)
    tasks.enfileirar_notificacao(1)


def test_exclusao_registra_motivo_no_historico(user):
    item = ItemFactory(owner=user)
    item.delete()
    assert item.history.first().history_change_reason == "Exclusão lógica"
    item.undelete()
    assert item.history.first().history_change_reason == "Restauração"
