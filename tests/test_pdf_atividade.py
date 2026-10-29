import io

import pytest
from django.urls import reverse
from pypdf import PdfReader
from rest_framework import status

from apps.pedagogico.models import AtividadeVariacao
from tests.factories import AtividadeFactory, TurmaFactory, UserFactory


@pytest.mark.django_db
def test_pdf_variacao_estilizada_contem_cabecalho_escolar_e_campos_aluno(auth_client):
    professor = UserFactory()
    turma = TurmaFactory(professores=[professor], nome="1º Ano A")
    atividade = AtividadeFactory(
        turma=turma,
        criada_por=professor,
        titulo="Atividade de Alfabetização: Encontro Vocálico",
        objetivo="Identificar encontros vocálicos em palavras simples.",
    )
    variacao = AtividadeVariacao.objects.create(
        atividade=atividade,
        numero=1,
        rotulo="prova_v1",
        eh_geral=True,
        conteudo=(
            "1. Leia as palavras abaixo e circule os encontros vocálicos:\npeixe, flauta, noite."
        ),
    )
    auth_client.force_authenticate(user=professor)

    url = reverse("variacao-pdf", args=[variacao.id])
    resposta = auth_client.get(url)

    assert resposta.status_code == status.HTTP_200_OK
    assert resposta["Content-Type"] == "application/pdf"
    assert "prova_v1-atividade-" in resposta["Content-Disposition"]

    leitor = PdfReader(io.BytesIO(resposta.content))
    assert len(leitor.pages) >= 1

    texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)
    assert "Estudante:" in texto
    assert "Data:" in texto
    assert "1º Ano A" in texto
    assert "prova_v1" in texto
    assert "Atividade de Alfabetização: Encontro Vocálico" in texto
    assert "peixe, flauta, noite" in texto
    assert "Marsupi" in texto


@pytest.mark.django_db
def test_pdf_variacao_diagrama_questoes_desenho_e_alternativas(auth_client):
    professor = UserFactory()
    turma = TurmaFactory(professores=[professor])
    atividade = AtividadeFactory(
        turma=turma,
        criada_por=professor,
        titulo="Ciências: Os Seres Vivos",
    )
    conteudo_rico = (
        "1. Escreva qual é o animal que late:\n"
        "2. Desenhe uma planta no quadro abaixo:\n"
        "3. Marque a alternativa correta:\n"
        "a) O gato é um ser vivo.\n"
        "b) A pedra é um ser vivo."
    )
    variacao = AtividadeVariacao.objects.create(
        atividade=atividade,
        numero=2,
        rotulo="prova_v2",
        eh_geral=False,
        conteudo=conteudo_rico,
    )
    auth_client.force_authenticate(user=professor)

    url = reverse("variacao-pdf", args=[variacao.id])
    resposta = auth_client.get(url)

    assert resposta.status_code == status.HTTP_200_OK
    leitor = PdfReader(io.BytesIO(resposta.content))
    texto = "\n".join(pagina.extract_text() or "" for pagina in leitor.pages)

    assert "1. Escreva qual é o animal que late:" in texto
    assert "2. Desenhe uma planta no quadro abaixo:" in texto
    assert "Espaço para desenho" in texto
    assert "O gato é um ser vivo" in texto


@pytest.mark.django_db
def test_pdf_atividade_endpoint_individual_e_em_lote(auth_client):
    professor = UserFactory()
    turma = TurmaFactory(professores=[professor])
    atividade = AtividadeFactory(
        turma=turma,
        criada_por=professor,
        titulo="Matemática Divertida",
        texto_original="1. Resolva as somas simples.",
    )
    # Cria 2 variações aprovadas e 1 rascunho
    AtividadeVariacao.objects.create(
        atividade=atividade,
        numero=1,
        rotulo="prova_v1",
        eh_geral=True,
        status="aprovada",
        conteudo="Versão geral: resolva 2 + 2.",
    )
    AtividadeVariacao.objects.create(
        atividade=atividade,
        numero=2,
        rotulo="prova_v2",
        eh_geral=False,
        status="aprovada",
        conteudo="Versão com apoio visual: conte os dedos 2 + 2.",
    )
    AtividadeVariacao.objects.create(
        atividade=atividade,
        numero=3,
        rotulo="prova_v3_rascunho",
        eh_geral=False,
        status="rascunho",
        conteudo="Versão rascunho que não deve sair na impressão em lote.",
    )
    auth_client.force_authenticate(user=professor)

    url_individual = reverse("atividade-pdf", args=[atividade.id])
    resp_ind = auth_client.get(url_individual)
    assert resp_ind.status_code == status.HTTP_200_OK
    assert resp_ind["Content-Type"] == "application/pdf"
    assert f"atividade-{atividade.id}.pdf" in resp_ind["Content-Disposition"]

    leitor_ind = PdfReader(io.BytesIO(resp_ind.content))
    texto_ind = "\n".join(pagina.extract_text() or "" for pagina in leitor_ind.pages)
    assert "Versão geral" in texto_ind

    # Teste de lote (apenas variações aprovadas)
    url_lote = f"{url_individual}?todas=true"
    resp_lote = auth_client.get(url_lote)
    assert resp_lote.status_code == status.HTTP_200_OK
    assert f"atividade-{atividade.id}-lote.pdf" in resp_lote["Content-Disposition"]

    leitor_lote = PdfReader(io.BytesIO(resp_lote.content))
    texto_lote = "\n".join(pagina.extract_text() or "" for pagina in leitor_lote.pages)
    assert "prova_v1" in texto_lote
    assert "prova_v2" in texto_lote
    assert "Versão com apoio visual" in texto_lote
    assert "prova_v3_rascunho" not in texto_lote
    assert "Versão rascunho" not in texto_lote


@pytest.mark.django_db
def test_pdf_atividade_isolamento_por_professor(auth_client):
    prof_a = UserFactory()
    prof_b = UserFactory()
    turma_a = TurmaFactory(professores=[prof_a])
    atividade_a = AtividadeFactory(turma=turma_a, criada_por=prof_a)

    auth_client.force_authenticate(user=prof_b)
    url = reverse("atividade-pdf", args=[atividade_a.id])
    resposta = auth_client.get(url)

    assert resposta.status_code == status.HTTP_404_NOT_FOUND


def test_pdf_atividade_exige_login(client):
    url = reverse("atividade-pdf", args=[1])
    resposta = client.get(url)
    assert resposta.status_code == status.HTTP_401_UNAUTHORIZED
