"""Variações alinhadas ao teste da IA (teste_ia_marsupi): regras do prompt,
metadados do aluno como perfil e adaptações registradas para a professora."""

import json

import pytest
from django.urls import reverse
from rest_framework import status

from apps.pedagogico.models import AtividadeVariacao
from apps.pedagogico.services import agrupar_perfis_apoio
from apps.pedagogico.services.variacoes import PROMPT_VARIACAO_ATIVIDADE

from .factories import (
    AlunoFactory,
    AtividadeFactory,
    EscolaFactory,
    MetaDadosFactory,
    TurmaFactory,
)

pytestmark = pytest.mark.django_db


def test_prompt_mantem_questoes_numeros_e_nao_revela_adaptacao():
    prompt = PROMPT_VARIACAO_ATIVIDADE
    assert "TODAS as questões" in prompt
    assert "TODOS os números" in prompt
    assert "versão adaptada" in prompt
    assert "adaptacoes_feitas" in prompt


def test_aluno_sem_perfil_de_apoio_usa_metadados_e_ignora_disc():
    turma = TurmaFactory()
    meta = MetaDadosFactory(
        perfil_disc="D",
        caracteristicas={"necessidades": ["Instruções curtas"], "hobby": "astronomia"},
    )
    aluno = AlunoFactory(turma=turma, nome="Aluno Meta", meta_dados=meta)
    sem_nada = AlunoFactory(turma=turma, nome="Aluno Sem Nada")

    geral, grupos = agrupar_perfis_apoio([aluno, sem_nada])

    assert geral == [sem_nada]
    assert len(grupos) == 1
    assert grupos[0].alunos == [aluno]
    assert grupos[0].necessidades == ["Instruções curtas"]
    assert any("astronomia" in e for e in grupos[0].estrategias)
    assert not any("Dominância" in e or "DISC" in e for e in grupos[0].estrategias)


def test_gerar_variacoes_registra_adaptacoes_e_envia_regras(auth_client, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()
    turma = TurmaFactory(escola=user.escola, professores=[user])
    meta = MetaDadosFactory(caracteristicas={"necessidades": ["Apoio visual"]})
    AlunoFactory(turma=turma, nome="Bruno Almeida", meta_dados=meta)
    AlunoFactory(turma=turma, nome="Lara Geral")
    atividade = AtividadeFactory(
        turma=turma,
        criada_por=user,
        titulo="Problemas",
        texto_original="1) 8 + 5 = ?\n2) 12 - 7 = ?",
    )
    enviados = []

    def fake_gemini(conteudo, api_key, modelo):
        enviados.append(conteudo)
        return json.dumps(
            {
                "conteudo": "1) 8 + 5 = ? (use os desenhos)\n2) 12 - 7 = ?",
                "adaptacoes_feitas": ["Acrescentado apoio visual na questão 1"],
            }
        )

    monkeypatch.setattr("apps.pedagogico.services.variacoes._pedir_ao_gemini", fake_gemini)

    resp = auth_client.post(reverse("atividade-gerar-variacoes", args=[atividade.id]))

    assert resp.status_code in (status.HTTP_200_OK, status.HTTP_201_CREATED), resp.json()
    assert len(enviados) == 1
    assert "Bruno" not in enviados[0]
    assert "TODOS os números" in enviados[0]
    adaptada = AtividadeVariacao.objects.get(atividade=atividade, eh_geral=False)
    assert adaptada.adaptacoes_feitas == ["Acrescentado apoio visual na questão 1"]
    assert "8" in adaptada.conteudo and "12" in adaptada.conteudo
