"""Responsável envia o laudo e confere o perfil de apoio pelo token do código."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.alunos.models import Consentimento
from apps.escolas.models import Config, Escola
from apps.pedagogico.models import PerfilApoio

from .factories import AlunoFactory, TurmaFactory

PDF_BYTES = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


@pytest.fixture
def aluno(user):
    config = Config.objects.create(api_key="chave-teste", modelo="gemini-3.8-flash")
    escola = Escola.objects.create(nome="Escola Teste", config=config)
    turma = TurmaFactory(professores=[user], escola=escola)
    return AlunoFactory(turma=turma, nome="João da Silva", consentimento=False)


def cliente_responsavel(auth_client, aluno):
    codigo = auth_client.post(reverse("aluno-codigo-acesso", args=[aluno.pk])).json()["codigo"]
    token = (
        APIClient()
        .post(reverse("responsavel-acesso"), {"codigo": codigo, "nome": "Maria"}, format="json")
        .json()["token"]
    )
    cliente = APIClient()
    cliente.credentials(HTTP_AUTHORIZATION=f"Responsavel {token}")
    return cliente


def fake_gemini(monkeypatch):
    def fake(arquivo_bytes, mime, api_key, modelo):
        return json.dumps(
            {
                "nome_no_documento": "João da Silva",
                "necessidades": ["Apoio na leitura"],
                "estrategias": ["Instruções curtas"],
                "observacoes": "",
            }
        )

    monkeypatch.setattr("apps.alunos.services.laudo._pedir_laudo_ao_gemini", fake)


def laudo():
    return SimpleUploadedFile("laudo.pdf", PDF_BYTES, content_type="application/pdf")


def test_sem_token_retorna_401():
    resp = APIClient().post(reverse("responsavel-laudo"), {"arquivo": laudo()}, format="multipart")
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


def test_sem_consentimento_retorna_403(auth_client, aluno, monkeypatch):
    fake_gemini(monkeypatch)
    cliente = cliente_responsavel(auth_client, aluno)
    resp = cliente.post(reverse("responsavel-laudo"), {"arquivo": laudo()}, format="multipart")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert not PerfilApoio.objects.filter(aluno=aluno).exists()


def test_envia_laudo_confere_e_corrige_perfil(auth_client, aluno, monkeypatch):
    fake_gemini(monkeypatch)
    cliente = cliente_responsavel(auth_client, aluno)
    assert cliente.post(reverse("responsavel-consentimento")).status_code == 201

    resp = cliente.post(reverse("responsavel-laudo"), {"arquivo": laudo()}, format="multipart")
    assert resp.status_code == status.HTTP_200_OK, resp.content
    corpo = resp.json()
    assert corpo["nome_conferiu"] is True
    assert corpo["perfil_apoio"]["necessidades"] == ["Apoio na leitura"]

    perfil = cliente.get(reverse("responsavel-perfil-apoio"))
    assert perfil.status_code == 200
    assert perfil.json()["id"] == corpo["perfil_apoio"]["id"]

    editado = cliente.patch(
        reverse("responsavel-perfil-apoio"),
        {"necessidades": ["Apoio na leitura em voz alta"], "observacoes": "Usa óculos"},
        format="json",
    )
    assert editado.status_code == 200
    perfil_db = PerfilApoio.objects.get(pk=corpo["perfil_apoio"]["id"])
    assert perfil_db.necessidades == ["Apoio na leitura em voz alta"]
    assert perfil_db.estrategias == ["Instruções curtas"]
    assert perfil_db.observacoes == "Usa óculos"


def test_perfil_so_do_aluno_do_token(auth_client, user, aluno):
    outro = AlunoFactory(turma=aluno.turma, consentimento=False)
    PerfilApoio.objects.create(aluno=outro, necessidades=["x"], estrategias=[], ativo=True)
    Consentimento.objects.create(aluno=aluno, aceito_em=timezone.now())
    cliente = cliente_responsavel(auth_client, aluno)
    assert cliente.get(reverse("responsavel-perfil-apoio")).status_code == 404
    assert cliente.patch(reverse("responsavel-perfil-apoio"), {}, format="json").status_code == 404
