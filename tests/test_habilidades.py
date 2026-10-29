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
from tests.factories import (
    AlunoFactory,
    AtividadeFactory,
    EnvioTrabalhosFactory,
    TrabalhoFactory,
    TurmaFactory,
    UserFactory,
)

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


def test_aluno_habilidades_exige_login(api_client):
    assert api_client.get("/api/alunos/1/habilidades/").status_code == status.HTTP_401_UNAUTHORIZED


def test_turma_habilidades_exige_login(api_client):
    assert api_client.get("/api/turmas/1/habilidades/").status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_aluno_habilidades_outro_professor_retorna_404(auth_client):
    prof1 = UserFactory()
    prof2 = UserFactory()
    turma2 = TurmaFactory(professores=[prof2])
    aluno2 = AlunoFactory(turma=turma2)
    auth_client.force_authenticate(user=prof1)
    resp = auth_client.get(f"/api/alunos/{aluno2.id}/habilidades/")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_turma_habilidades_outro_professor_retorna_404(auth_client):
    prof1 = UserFactory()
    prof2 = UserFactory()
    turma2 = TurmaFactory(professores=[prof2])
    auth_client.force_authenticate(user=prof1)
    resp = auth_client.get(f"/api/turmas/{turma2.id}/habilidades/")
    assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_aluno_habilidades_sem_consentimento_retorna_403(auth_client):
    prof = UserFactory()
    turma = TurmaFactory(professores=[prof])
    aluno = AlunoFactory(turma=turma, consentimento=False)
    auth_client.force_authenticate(user=prof)
    resp = auth_client.get(f"/api/alunos/{aluno.id}/habilidades/")
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    assert "consentimento" in resp.json()["erro"].lower()


@pytest.mark.django_db
def test_aluno_habilidades_regra_dois_trabalhos_e_ultimo_trabalho(auth_client):
    prof = UserFactory()
    turma = TurmaFactory(professores=[prof])
    aluno = AlunoFactory(turma=turma)
    atividade = AtividadeFactory(turma=turma, criada_por=prof)
    envio = EnvioTrabalhosFactory(atividade=atividade, enviado_por=prof)
    auth_client.force_authenticate(user=prof)

    # Trabalho 1: LP-ALFABETO a reforçar, MA-CONT demonstrada
    TrabalhoFactory(
        envio=envio,
        aluno=aluno,
        habilidades_a_reforcar=["LP-ALFABETO"],
        habilidades_demonstradas=["MA-CONT"],
        status=Trabalho.StatusChoices.ANALISADO,
    )
    # Trabalho 2: LP-ALFABETO a reforçar (atinge 2), MA-CONT a reforçar (atinge 1)
    TrabalhoFactory(
        envio=envio,
        aluno=aluno,
        habilidades_a_reforcar=["LP-ALFABETO", "MA-CONT"],
        habilidades_demonstradas=[],
        status=Trabalho.StatusChoices.ANALISADO,
    )

    resp = auth_client.get(f"/api/alunos/{aluno.id}/habilidades/")
    assert resp.status_code == status.HTTP_200_OK
    dados = resp.json()
    assert len(dados) == len(HABILIDADES)

    mapa = {item["codigo"]: item for item in dados}

    # LP-ALFABETO apareceu em 2 trabalhos a reforçar -> em_reforco=True
    assert mapa["LP-ALFABETO"]["trabalhos_a_reforcar"] == 2
    assert mapa["LP-ALFABETO"]["trabalhos_demonstrada"] == 0
    assert mapa["LP-ALFABETO"]["em_reforco"] is True
    assert mapa["LP-ALFABETO"]["ultimo_trabalho_em"] is not None

    # MA-CONT apareceu em 1 demonstrada e 1 a reforçar -> em_reforco=False
    assert mapa["MA-CONT"]["trabalhos_a_reforcar"] == 1
    assert mapa["MA-CONT"]["trabalhos_demonstrada"] == 1
    assert mapa["MA-CONT"]["em_reforco"] is False

    # Habilidade sem trabalho -> tudo 0 e ultimo_trabalho_em None
    assert mapa["MA-SEQ"]["trabalhos_a_reforcar"] == 0
    assert mapa["MA-SEQ"]["trabalhos_demonstrada"] == 0
    assert mapa["MA-SEQ"]["em_reforco"] is False
    assert mapa["MA-SEQ"]["ultimo_trabalho_em"] is None


@pytest.mark.django_db
def test_turma_habilidades_resumo_sem_nomes_e_ignora_sem_consentimento(auth_client):
    prof = UserFactory()
    turma = TurmaFactory(professores=[prof])
    aluno1 = AlunoFactory(turma=turma, nome="Aluno Um")
    aluno2 = AlunoFactory(turma=turma, nome="Aluno Dois")
    aluno3 = AlunoFactory(turma=turma, nome="Aluno Tres", consentimento=False)

    atividade = AtividadeFactory(turma=turma, criada_por=prof)
    envio = EnvioTrabalhosFactory(atividade=atividade, enviado_por=prof)
    auth_client.force_authenticate(user=prof)

    # Aluno 1: 2 trabalhos com LP-ALFABETO -> em_reforco=True
    TrabalhoFactory(envio=envio, aluno=aluno1, habilidades_a_reforcar=["LP-ALFABETO"])
    TrabalhoFactory(envio=envio, aluno=aluno1, habilidades_a_reforcar=["LP-ALFABETO"])

    # Aluno 2: 1 trabalho com LP-ALFABETO (não atinge 2), 2 com MA-NUM-ESCR -> em_reforco=True
    TrabalhoFactory(
        envio=envio,
        aluno=aluno2,
        habilidades_a_reforcar=["LP-ALFABETO", "MA-NUM-ESCR"],
    )
    TrabalhoFactory(envio=envio, aluno=aluno2, habilidades_a_reforcar=["MA-NUM-ESCR"])

    # Aluno 3 (sem consentimento): 3 trabalhos com LP-ALFABETO -> DEVE SER IGNORADO
    TrabalhoFactory(envio=envio, aluno=aluno3, habilidades_a_reforcar=["LP-ALFABETO"])
    TrabalhoFactory(envio=envio, aluno=aluno3, habilidades_a_reforcar=["LP-ALFABETO"])

    resp = auth_client.get(f"/api/turmas/{turma.id}/habilidades/")
    assert resp.status_code == status.HTTP_200_OK
    dados = resp.json()
    assert len(dados) == len(HABILIDADES)

    mapa = {item["codigo"]: item for item in dados}
    # LP-ALFABETO: somente Aluno 1 tem >= 2 trabalhos (Aluno 2 tem 1, Aluno 3 não tem consentimento)
    assert mapa["LP-ALFABETO"]["total_alunos_reforco"] == 1
    # MA-NUM-ESCR: somente Aluno 2 tem >= 2 trabalhos
    assert mapa["MA-NUM-ESCR"]["total_alunos_reforco"] == 1
    # MA-SEQ: nenhum aluno
    assert mapa["MA-SEQ"]["total_alunos_reforco"] == 0

    # Garante que nenhum nome de aluno foi exposto no payload agregado (LGPD)
    payload_str = json.dumps(dados, ensure_ascii=False)
    assert "Aluno Um" not in payload_str
    assert "Aluno Dois" not in payload_str
    assert "Aluno Tres" not in payload_str
    assert "dificuldade" not in payload_str.lower()


@pytest.mark.django_db
def test_trabalho_pendente_nao_entra_no_calculo_de_habilidades(auth_client):
    prof = UserFactory()
    turma = TurmaFactory(professores=[prof])
    aluno = AlunoFactory(turma=turma, nome="Lucas Teste")
    atividade = AtividadeFactory(turma=turma, criada_por=prof)
    envio = EnvioTrabalhosFactory(atividade=atividade, enviado_por=prof)
    auth_client.force_authenticate(user=prof)

    # 1 trabalho confirmado + 1 trabalho com identificacao pendente
    TrabalhoFactory(
        envio=envio,
        aluno=aluno,
        identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
        habilidades_a_reforcar=["LP-ALFABETO"],
    )
    TrabalhoFactory(
        envio=envio,
        aluno=aluno,
        identificacao=Trabalho.IdentificacaoChoices.PENDENTE,
        habilidades_a_reforcar=["LP-ALFABETO"],
    )

    # No cálculo individual do aluno, o pendente NÃO deve contar (total deve ser 1, não 2)
    resp_aluno = auth_client.get(f"/api/alunos/{aluno.id}/habilidades/")
    assert resp_aluno.status_code == status.HTTP_200_OK
    hab_aluno = next(h for h in resp_aluno.json() if h["codigo"] == "LP-ALFABETO")
    assert hab_aluno["trabalhos_a_reforcar"] == 1
    assert hab_aluno["em_reforco"] is False

    # No cálculo da turma, o aluno também NÃO deve constar em reforço
    resp_turma = auth_client.get(f"/api/turmas/{turma.id}/habilidades/")
    assert resp_turma.status_code == status.HTTP_200_OK
    hab_turma = next(h for h in resp_turma.json() if h["codigo"] == "LP-ALFABETO")
    assert hab_turma["total_alunos_reforco"] == 0
