"""Professor sem escola: a IA e a criação de turma descobrem a escola sozinhas."""

import io

import pytest
from PIL import Image

from apps.escolas.models import Escola, Turma
from apps.escolas.services.escola_usuario import config_ia_do_usuario, escola_do_usuario

from .factories import ConfigFactory, EscolaFactory, TurmaFactory, UserFactory

pytestmark = pytest.mark.django_db


def _png():
    buffer = io.BytesIO()
    Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
    buffer.seek(0)
    buffer.name = "chamada.png"
    return buffer


def test_unica_escola_vira_a_escola_do_professor(user):
    escola = EscolaFactory()

    assert escola_do_usuario(user) == escola
    user.refresh_from_db()
    assert user.escola == escola


def test_escola_vem_das_turmas_do_professor(user):
    EscolaFactory()
    outra = EscolaFactory()
    TurmaFactory(escola=outra, professores=[user])

    assert escola_do_usuario(user) == outra


def test_varias_escolas_sem_turma_nao_adivinha(user):
    EscolaFactory()
    EscolaFactory()

    assert escola_do_usuario(user) is None
    assert config_ia_do_usuario(user) is None


def test_escola_sem_config_usa_a_unica_config_com_chave():
    professor = UserFactory()
    escola = Escola.objects.create(nome="Escola sem config", endereco="Rua 1")
    config = ConfigFactory(api_key="chave-unica")

    assert config_ia_do_usuario(professor) == config
    escola.refresh_from_db()
    assert escola.config == config


def test_chamada_funciona_para_professor_sem_escola(auth_client, user, monkeypatch):
    EscolaFactory(config=ConfigFactory(api_key="chave-da-escola"))
    capturado = {}

    def fake_ocr(imagem_bytes, mime, api_key, modelo):
        capturado["api_key"] = api_key
        return '{"nomes": [{"nome": "Alice Souza", "confianca": 0.9}]}'

    monkeypatch.setattr("apps.escolas.services.chamada._pedir_ocr_ao_gemini", fake_ocr)

    resp = auth_client.post("/api/chamada/reconhecer/", {"imagem": _png()}, format="multipart")

    assert resp.status_code == 200
    assert capturado["api_key"] == "chave-da-escola"


def test_criar_turma_sem_escola_no_payload_para_professor_sem_escola(auth_client, user):
    escola = EscolaFactory()

    resp = auth_client.post(
        "/api/turmas/",
        {"nome": "1º ano A", "turno": "manha", "ano_letivo": 2026, "alunos": ["Ana", "Bruno"]},
        format="json",
    )

    assert resp.status_code == 201, resp.json()
    turma = Turma.objects.get(pk=resp.json()["id"])
    assert turma.escola == escola
    assert turma.alunos.count() == 2
    assert user in turma.professores.all()
