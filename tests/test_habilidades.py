import json
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from apps.pedagogico.models import Relatorio, Trabalho
from apps.pedagogico.services.habilidades import (
    CODIGOS_HABILIDADES,
    HABILIDADES,
    filtrar_codigos,
)
from tests.factories import AlunoFactory, AtividadeFactory, TurmaFactory, UserFactory

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def test_lista_de_habilidades_e_fixa_e_tem_codigos_unicos():
    assert 10 <= len(HABILIDADES) <= 15
    assert len(CODIGOS_HABILIDADES) == len(HABILIDADES)
    assert {h["area"] for h in HABILIDADES} == {"Língua Portuguesa", "Matemática"}


def test_filtrar_codigos_descarta_fora_da_lista_e_repetidos():
    assert filtrar_codigos(["ma-cont", "INVENTADO", "MA-CONT", "LP-INTERP", None]) == [
        "MA-CONT",
        "LP-INTERP",
    ]
    assert filtrar_codigos("MA-CONT") == []
    assert filtrar_codigos(["MA-CONT", "LP-INTERP", "MA-SEQ"], limite=2) == [
        "MA-CONT",
        "LP-INTERP",
    ]


def test_endpoint_habilidades_exige_login(api_client):
    assert api_client.get("/api/habilidades/").status_code == status.HTTP_401_UNAUTHORIZED


def test_endpoint_habilidades_lista_tudo(auth_client):
    resp = auth_client.get("/api/habilidades/")
    assert resp.status_code == status.HTTP_200_OK
    assert [h["codigo"] for h in resp.json()] == [h["codigo"] for h in HABILIDADES]


@pytest.mark.django_db
def test_analise_devolve_so_codigos_validos_e_prompt_sem_diagnostico():
    from apps.pedagogico.services.trabalhos import analisar_trabalho_com_gemini

    resposta = json.dumps(
        {
            "nome_lido": "Ana",
            "descricao": "Contou objetos.",
            "habilidades_demonstradas": ["MA-CONT", "INVENTADO"],
            "habilidades_a_reforcar": ["MA-ADI-SUB", "LP-INTERP", "MA-SEQ", "MA-PROB"],
            "analise_pedagogica": {"pontos_fortes": ["Contagem"]},
        }
    )
    with patch("google.genai.Client") as cliente:
        cliente.return_value.models.generate_content.return_value.text = resposta
        resultado = analisar_trabalho_com_gemini(
            conteudo=PDF, mime_type="application/pdf", nome_arquivo="t.pdf", api_key="x"
        )

    assert resultado["habilidades_demonstradas"] == ["MA-CONT"]
    assert resultado["habilidades_a_reforcar"] == ["MA-ADI-SUB", "LP-INTERP", "MA-SEQ"]

    prompt = cliente.return_value.models.generate_content.call_args.kwargs["contents"][1]
    for codigo in CODIGOS_HABILIDADES:
        assert codigo in prompt
    assert "NUNCA faça diagnóstico" in prompt
    assert "dificuldades_identificadas" not in prompt


@pytest.mark.django_db
def test_envio_grava_habilidades_no_trabalho_e_no_relatorio(auth_client):
    professor = UserFactory()
    turma = TurmaFactory(professores=[professor])
    aluno = AlunoFactory(turma=turma, nome="Lucas Gabriel Silva")
    atividade = AtividadeFactory(turma=turma, criada_por=professor)
    auth_client.force_authenticate(user=professor)

    retorno = {
        "nome_lido": "Lucas Gabriel Silva",
        "descricao": "Somas simples.",
        "analise_pedagogica": {},
        "habilidades_demonstradas": ["MA-CONT"],
        "habilidades_a_reforcar": ["MA-ADI-SUB"],
    }
    with (
        patch(
            "apps.pedagogico.services.trabalhos._obter_credenciais_llm",
            return_value=("chave", "modelo"),
        ),
        patch(
            "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
            return_value=retorno,
        ),
    ):
        resp = auth_client.post(
            f"/api/atividades/{atividade.id}/trabalhos/",
            {"arquivos": [SimpleUploadedFile("t.pdf", PDF, content_type="application/pdf")]},
            format="multipart",
        )

    assert resp.status_code == status.HTTP_201_CREATED, resp.content
    trabalho = Trabalho.objects.get(aluno=aluno)
    assert trabalho.habilidades_demonstradas == ["MA-CONT"]
    assert trabalho.habilidades_a_reforcar == ["MA-ADI-SUB"]
    assert resp.json()["trabalhos"][0]["habilidades_a_reforcar"] == ["MA-ADI-SUB"]
    relatorio = Relatorio.objects.get(aluno=aluno)
    assert relatorio.dados["habilidades_a_reforcar"] == [
        {"codigo": "MA-ADI-SUB", "nome": "Resolver adições e subtrações simples"}
    ]
