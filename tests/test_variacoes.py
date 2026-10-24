from io import BytesIO

import pytest
from django.urls import reverse
from pypdf import PdfReader
from rest_framework import status

from apps.pedagogico.models import Atividade, AtividadeVariacao, VariacaoAluno
from apps.pedagogico.services import agrupar_perfis_apoio

from .factories import (
    AlunoFactory,
    AtividadeFactory,
    AtividadeVariacaoFactory,
    EscolaFactory,
    PerfilApoioFactory,
    ResponsavelFactory,
    TurmaFactory,
    VariacaoAlunoFactory,
)

pytestmark = pytest.mark.django_db


def test_agrupamento_perfis_apoio_limita_em_4_grupos_adaptados():
    turma = TurmaFactory()
    aluno_sem_perfil = AlunoFactory(turma=turma, nome="Aluno Geral")
    aluno_perfil_inativo = AlunoFactory(turma=turma, nome="Aluno Inativo")
    PerfilApoioFactory(
        aluno=aluno_perfil_inativo,
        necessidades=["Apoio visual"],
        ativo=False,
    )

    # 2 alunos com a mesma necessidade (devem cair no mesmo grupo)
    a1 = AlunoFactory(turma=turma, nome="Aluno A1")
    a2 = AlunoFactory(turma=turma, nome="Aluno A2")
    PerfilApoioFactory(aluno=a1, necessidades=["Pistas visuais em etapas"])
    PerfilApoioFactory(aluno=a2, necessidades=["Pistas visuais em etapas"])

    # Mais 5 alunos com necessidades distintas (total 6 perfis distintos -> mescla para 4)
    necessidades_distintas = [
        ["Enunciados curtos e objetivos", "Fonte ampliada"],
        ["Enunciados curtos e destaque em palavras-chave"],
        ["Tempo adicional e pausas ativas"],
        ["Pausas ativas e divisão em blocos"],
        ["Uso de material concreto e esquemas"],
    ]
    outros_alunos = []
    for idx, nec in enumerate(necessidades_distintas):
        aluno = AlunoFactory(turma=turma, nome=f"Aluno Extra {idx}")
        PerfilApoioFactory(aluno=aluno, necessidades=nec)
        outros_alunos.append(aluno)

    todos = [aluno_sem_perfil, aluno_perfil_inativo, a1, a2, *outros_alunos]
    alunos_geral, grupos = agrupar_perfis_apoio(todos)

    assert set(alunos_geral) == {aluno_sem_perfil, aluno_perfil_inativo}
    assert len(grupos) == 4
    alunos_agrupados = [a for g in grupos for a in g.alunos]
    assert set(alunos_agrupados) == {a1, a2, *outros_alunos}


def test_gerar_variacoes_cria_versoes_neutras_sem_pii_e_regera_rascunhos(
    auth_client, user, monkeypatch
):
    user.escola = EscolaFactory()
    user.save()
    turma = TurmaFactory(escola=user.escola, professores=[user])

    resp = ResponsavelFactory(nome="Maria Souza", cpf="12345678901")
    aluno_geral = AlunoFactory(turma=turma, nome="Pedro Geral", responsavel=resp)
    aluno_apoio_1 = AlunoFactory(turma=turma, nome="Lucas Silva", responsavel=resp)
    aluno_apoio_2 = AlunoFactory(turma=turma, nome="Carla Lima", responsavel=resp)

    # Inclui termos clínicos/CID que devem ser filtrados antes de ir à LLM
    PerfilApoioFactory(
        aluno=aluno_apoio_1,
        necessidades=["Enunciados curtos CID-10 F90.0 TDAH", "Pistas visuais"],
        estrategias=["Dividir em etapas numeradas"],
    )
    PerfilApoioFactory(
        aluno=aluno_apoio_2,
        necessidades=["Enunciados curtos", "Pistas visuais"],
        estrategias=["Dividir em etapas numeradas"],
    )

    atividade = AtividadeFactory(
        turma=turma,
        criada_por=user,
        titulo="Problemas de Frações",
        texto_original="Lucas Silva resolveu 2/4 do exercício em 10/03/2026 (CPF 123.456.789-01).",
        objetivo="Compreender frações equivalentes",
    )

    chamadas_llm = []

    def fake_gemini(conteudo, api_key, modelo):
        chamadas_llm.append(conteudo)
        return '{"conteudo": "1) Observe a figura e marque a fração equivalente a 1/2."}'

    monkeypatch.setattr("apps.pedagogico.services.variacoes._pedir_ao_gemini", fake_gemini)

    url = reverse("atividade-gerar-variacoes", args=[atividade.id])
    response = auth_client.post(url)

    assert response.status_code == status.HTTP_201_CREATED
    dados = response.json()
    assert len(dados) == 2

    v1, v2 = dados[0], dados[1]
    assert v1["numero"] == 1
    assert v1["rotulo"] == "prova_v1"
    assert v1["eh_geral"] is True
    assert v1["status"] == "rascunho"
    assert v1["alunos"] == [aluno_geral.id]

    assert v2["numero"] == 2
    assert v2["rotulo"] == "prova_v2"
    assert v2["eh_geral"] is False
    assert v2["status"] == "rascunho"
    assert set(v2["alunos"]) == {aluno_apoio_1.id, aluno_apoio_2.id}

    # Nenhum rótulo traz nome de aluno ou condição
    for var in dados:
        rotulo_lower = var["rotulo"].lower()
        assert "lucas" not in rotulo_lower
        assert "carla" not in rotulo_lower
        assert "tdah" not in rotulo_lower
        assert "cid" not in rotulo_lower

    # Verifica que o payload enviado à LLM não contém PII nem CID/diagnóstico
    assert len(chamadas_llm) == 1
    prompt_enviado = chamadas_llm[0].lower()
    assert "lucas" not in prompt_enviado
    assert "pedro" not in prompt_enviado
    assert "carla" not in prompt_enviado
    assert "maria" not in prompt_enviado
    assert "123.456.789-01" not in prompt_enviado
    assert "10/03/2026" not in prompt_enviado
    assert "f90.0" not in prompt_enviado

    atividade.refresh_from_db()
    assert atividade.status == Atividade.StatusChoices.VARIACOES_GERADAS

    # Regerar apaga as variações em rascunho antes e recria sem violar constraint
    ids_antigos = {v1["id"], v2["id"]}
    response_regerar = auth_client.post(url)
    assert response_regerar.status_code == status.HTTP_201_CREATED
    assert AtividadeVariacao.objects.filter(atividade=atividade).count() == 2
    ids_novos = {v["id"] for v in response_regerar.json()}
    assert ids_antigos.isdisjoint(ids_novos)


def test_editar_conteudo_marca_editada_manual_e_aprovar_variacao(auth_client, user):
    turma = TurmaFactory(professores=[user])
    atividade = AtividadeFactory(
        turma=turma,
        criada_por=user,
        status=Atividade.StatusChoices.VARIACOES_GERADAS,
    )
    variacao = AtividadeVariacaoFactory(
        atividade=atividade,
        numero=1,
        rotulo="prova_v1",
        eh_geral=True,
        conteudo="Conteúdo original",
        editada_manual=False,
    )

    # 1. PATCH em conteudo marca editada_manual = True
    url_detail = reverse("variacao-detail", args=[variacao.id])
    resp_patch = auth_client.patch(
        url_detail,
        {"conteudo": "Conteúdo revisado pela professora"},
        format="json",
    )
    assert resp_patch.status_code == status.HTTP_200_OK
    assert resp_patch.json()["conteudo"] == "Conteúdo revisado pela professora"
    assert resp_patch.json()["editada_manual"] is True

    # 2. POST /api/variacoes/{id}/aprovar/
    url_aprovar = reverse("variacao-aprovar", args=[variacao.id])
    resp_aprovar = auth_client.post(url_aprovar)
    assert resp_aprovar.status_code == status.HTTP_200_OK
    dados_aprov = resp_aprovar.json()
    assert dados_aprov["status"] == AtividadeVariacao.StatusChoices.APROVADA
    assert dados_aprov["aprovada_por"] == user.id
    assert dados_aprov["aprovada_em"] is not None

    atividade.refresh_from_db()
    assert atividade.status == Atividade.StatusChoices.APROVADA


def test_pdf_variacao_contem_rotulo_e_titulo_sem_nome_de_aluno_ou_condicao(auth_client, user):
    turma = TurmaFactory(professores=[user])
    aluno = AlunoFactory(turma=turma, nome="Gabriel Ribeiro")
    PerfilApoioFactory(
        aluno=aluno,
        necessidades=["Apoio visual em leitura"],
        observacoes="Observação interna da professora",
    )
    atividade = AtividadeFactory(
        turma=turma,
        criada_por=user,
        titulo="Avaliação de Geografia",
    )
    variacao = AtividadeVariacaoFactory(
        atividade=atividade,
        numero=2,
        rotulo="prova_v2",
        eh_geral=False,
        conteudo="Questão 1: Identifique os biomas brasileiros no mapa.",
    )
    VariacaoAlunoFactory(variacao=variacao, aluno=aluno)

    url_pdf = reverse("variacao-pdf", args=[variacao.id])
    response = auth_client.get(url_pdf)

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")

    leitor = PdfReader(BytesIO(response.content))
    texto_pdf = "\n".join(p.extract_text() or "" for p in leitor.pages)
    assert "prova_v2" in texto_pdf
    assert "Avaliação de Geografia" in texto_pdf
    assert "biomas brasileiros" in texto_pdf
    assert "Gabriel Ribeiro" not in texto_pdf
    assert "Gabriel" not in texto_pdf
    assert "Apoio visual" not in texto_pdf
    assert b"Gabriel" not in response.content


def test_mapa_variacoes_e_isolamento_por_professor(auth_client, user):
    minha_turma = TurmaFactory(professores=[user])
    meu_aluno = AlunoFactory(turma=minha_turma, nome="Helena Costa")
    minha_ativ = AtividadeFactory(turma=minha_turma, criada_por=user)
    minha_var = AtividadeVariacaoFactory(
        atividade=minha_ativ,
        numero=1,
        rotulo="prova_v1",
        eh_geral=True,
    )
    VariacaoAlunoFactory(variacao=minha_var, aluno=meu_aluno)

    outra_turma = TurmaFactory()
    outra_ativ = AtividadeFactory(turma=outra_turma)
    outra_var = AtividadeVariacaoFactory(atividade=outra_ativ, numero=1, rotulo="prova_v1")

    # Professor da turma vê o mapa (versão -> alunos)
    resp_mapa = auth_client.get(reverse("atividade-mapa-variacoes", args=[minha_ativ.id]))
    assert resp_mapa.status_code == status.HTTP_200_OK
    mapa = resp_mapa.json()
    assert len(mapa) == 1
    assert mapa[0]["rotulo"] == "prova_v1"
    assert mapa[0]["alunos"] == [{"id": meu_aluno.id, "nome": "Helena Costa"}]

    # Professor de outra turma recebe 404 em todas as ações
    assert (
        auth_client.get(reverse("atividade-mapa-variacoes", args=[outra_ativ.id])).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        auth_client.post(reverse("atividade-gerar-variacoes", args=[outra_ativ.id])).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        auth_client.post(reverse("variacao-aprovar", args=[outra_var.id])).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        auth_client.get(reverse("variacao-pdf", args=[outra_var.id])).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_gerar_variacoes_erro_llm_retorna_502(auth_client, user, monkeypatch):
    user.escola = EscolaFactory()
    user.save()
    turma = TurmaFactory(escola=user.escola, professores=[user])
    aluno = AlunoFactory(turma=turma)
    PerfilApoioFactory(aluno=aluno, necessidades=["Enunciados curtos"])
    atividade = AtividadeFactory(turma=turma, criada_por=user)

    def fake_erro(*args, **kwargs):
        raise RuntimeError("Falha Gemini")

    monkeypatch.setattr("apps.pedagogico.services.variacoes._pedir_ao_gemini", fake_erro)

    url = reverse("atividade-gerar-variacoes", args=[atividade.id])
    response = auth_client.post(url)
    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert "erro" in response.json()
    assert VariacaoAluno.objects.count() == 0
