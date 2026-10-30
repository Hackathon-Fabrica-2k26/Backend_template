import json

import pytest
from django.urls import reverse
from rest_framework import status

from apps.pedagogico.models import AtividadeVariacao, Trabalho
from apps.pedagogico.services import agrupar_perfis_apoio
from apps.pedagogico.services.variacoes import habilidade_principal_por_aluno

from .factories import (
    AlunoFactory,
    AtividadeFactory,
    EscolaFactory,
    PerfilApoioFactory,
    TrabalhoFactory,
    TurmaFactory,
)

pytestmark = pytest.mark.django_db


def _trabalhos(aluno, atividade, *listas):
    for codigos in listas:
        TrabalhoFactory(
            envio__atividade=atividade,
            aluno=aluno,
            identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
            habilidades_a_reforcar=list(codigos),
        )


def test_habilidade_principal_exige_dois_trabalhos():
    turma = TurmaFactory()
    atividade = AtividadeFactory(turma=turma)
    a1 = AlunoFactory(turma=turma)
    a2 = AlunoFactory(turma=turma)
    _trabalhos(a1, atividade, ["MA-ADI-SUB", "LP-INTERP"], ["MA-ADI-SUB"], ["MA-ADI-SUB"])
    _trabalhos(a2, atividade, ["MA-CONT"])  # um trabalho só: ainda não forma grupo

    principal = habilidade_principal_por_aluno([a1, a2])

    assert principal == {a1.id: "MA-ADI-SUB"}


def test_agrupa_alunos_pela_habilidade_a_reforcar():
    turma = TurmaFactory()
    atividade = AtividadeFactory(turma=turma)
    soma1, soma2, leitura, sem = (AlunoFactory(turma=turma) for _ in range(4))
    for aluno in (soma1, soma2):
        _trabalhos(aluno, atividade, ["MA-ADI-SUB"], ["MA-ADI-SUB"])
    _trabalhos(leitura, atividade, ["LP-LEIT-FRASE"], ["LP-LEIT-FRASE"])

    geral, grupos = agrupar_perfis_apoio([soma1, soma2, leitura, sem])

    assert geral == [sem]
    por_habilidade = {g.habilidade: {a.id for a in g.alunos} for g in grupos}
    assert por_habilidade == {
        "MA-ADI-SUB": {soma1.id, soma2.id},
        "LP-LEIT-FRASE": {leitura.id},
    }


def test_perfil_de_apoio_vira_camada_de_formato_dentro_da_habilidade():
    turma = TurmaFactory()
    atividade = AtividadeFactory(turma=turma)
    com_apoio, sem_apoio = AlunoFactory(turma=turma), AlunoFactory(turma=turma)
    for aluno in (com_apoio, sem_apoio):
        _trabalhos(aluno, atividade, ["MA-ADI-SUB"], ["MA-ADI-SUB"])
    PerfilApoioFactory(aluno=com_apoio, necessidades=["Letra ampliada"], estrategias=[])

    _, grupos = agrupar_perfis_apoio([com_apoio, sem_apoio])

    assert len(grupos) == 2
    assert {g.habilidade for g in grupos} == {"MA-ADI-SUB"}
    formatos = {tuple(g.necessidades) for g in grupos}
    assert formatos == {("Letra ampliada",), ()}


def test_gerar_variacoes_envia_habilidade_e_grava_na_versao(auth_client, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()
    turma = TurmaFactory(escola=user.escola, professores=[user])
    atividade = AtividadeFactory(turma=turma, criada_por=user, texto_original="1) 3 + 4 = ?")
    aluno = AlunoFactory(turma=turma, nome="Bruno Teixeira")
    _trabalhos(aluno, atividade, ["MA-ADI-SUB"], ["MA-ADI-SUB"])

    prompts = []

    def fake_gemini(conteudo, api_key, modelo):
        prompts.append(conteudo)
        return json.dumps(
            {"conteudo": "1) 3 + 4 = ? Dica: conte nos dedos.", "adaptacoes_feitas": []}
        )

    monkeypatch.setattr("apps.pedagogico.services.variacoes._pedir_ao_gemini", fake_gemini)

    resp = auth_client.post(reverse("atividade-gerar-variacoes", args=[atividade.id]))

    assert resp.status_code == status.HTTP_201_CREATED
    assert len(prompts) == 1
    assert "Resolver adições e subtrações simples" in prompts[0]
    assert "Bruno" not in prompts[0]
    adaptada = AtividadeVariacao.objects.get(atividade=atividade, eh_geral=False)
    assert adaptada.habilidade == "MA-ADI-SUB"

    mapa = auth_client.get(reverse("atividade-mapa-variacoes", args=[atividade.id])).json()
    item = next(i for i in mapa if not i["eh_geral"])
    assert item["habilidade_nome"] == "Resolver adições e subtrações simples"
    assert [a["id"] for a in item["alunos"]] == [aluno.id]
