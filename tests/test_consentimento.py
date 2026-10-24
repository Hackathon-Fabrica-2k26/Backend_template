from unittest.mock import patch

import pytest
from rest_framework import status

from apps.alunos.models import Consentimento
from apps.alunos.services import tem_consentimento_ativo
from apps.pedagogico.models import PerfilApoio, Relatorio, Trabalho
from tests.factories import (
    AlunoFactory,
    AtividadeFactory,
    ConsentimentoFactory,
    PerfilApoioFactory,
    RelatorioFactory,
    TrabalhoFactory,
    TurmaFactory,
)

URL = "/api/consentimentos/"


@pytest.fixture
def cenario(db, auth_client, user):
    turma = TurmaFactory(professores=[user])
    aluno = AlunoFactory(turma=turma, consentimento=False)
    return {"turma": turma, "aluno": aluno}


def test_consentimento_exige_autenticacao(api_client):
    assert api_client.get(URL).status_code == status.HTTP_401_UNAUTHORIZED


def test_criar_consentimento_registra_dados(auth_client, cenario):
    resp = auth_client.post(URL, {"aluno": cenario["aluno"].pk}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["ativo"] is True
    assert resp.data["versao_texto"]
    assert resp.data["aceito_em"]
    assert tem_consentimento_ativo(cenario["aluno"])


def test_criar_consentimento_duplicado_retorna_400(auth_client, cenario):
    ConsentimentoFactory(aluno=cenario["aluno"])
    resp = auth_client.post(URL, {"aluno": cenario["aluno"].pk}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_criar_consentimento_aluno_de_outra_turma_retorna_400(auth_client, cenario):
    outro = AlunoFactory(turma=TurmaFactory(), consentimento=False)
    resp = auth_client.post(URL, {"aluno": outro.pk}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_consentimento_de_outro_professor_retorna_404(auth_client, db):
    alheio = ConsentimentoFactory(aluno=AlunoFactory(turma=TurmaFactory(), consentimento=False))
    assert auth_client.get(f"{URL}{alheio.pk}/").status_code == status.HTTP_404_NOT_FOUND
    assert auth_client.post(f"{URL}{alheio.pk}/revogar/").status_code == status.HTTP_404_NOT_FOUND


def test_relatorio_gerar_sem_consentimento_bloqueia_ia(auth_client, cenario):
    with patch("apps.pedagogico.views.relatorio_gerar.gerar_relatorio") as llm:
        resp = auth_client.post(
            "/api/relatorios/gerar/",
            {"aluno": cenario["aluno"].pk, "pontos_fortes": ["a"], "desafios": ["b"]},
            format="json",
        )
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    llm.assert_not_called()


def test_gerar_variacoes_ignora_aluno_sem_consentimento(auth_client, user, cenario):
    from apps.pedagogico.models import VariacaoAluno

    com = AlunoFactory(turma=cenario["turma"])
    atividade = AtividadeFactory(turma=cenario["turma"], criada_por=user)
    from apps.pedagogico.services import gerar_variacoes_atividade

    gerar_variacoes_atividade(atividade, api_key="k")
    atribuidos = set(VariacaoAluno.objects.values_list("aluno_id", flat=True))
    assert atribuidos == {com.pk}


def test_confirmar_trabalho_sem_consentimento_retorna_400(auth_client, user, cenario):
    atividade = AtividadeFactory(turma=cenario["turma"], criada_por=user)
    trabalho = TrabalhoFactory(atividade=atividade, envio__atividade=atividade)
    resp = auth_client.patch(
        f"/api/trabalhos/{trabalho.pk}/", {"aluno": cenario["aluno"].pk}, format="json"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_revogar_apaga_dados_derivados_e_historico(auth_client, user, cenario):
    aluno = cenario["aluno"]
    consentimento = ConsentimentoFactory(aluno=aluno)
    atividade = AtividadeFactory(turma=cenario["turma"], criada_por=user)
    perfil = PerfilApoioFactory(aluno=aluno)
    relatorio = RelatorioFactory(aluno=aluno)
    trabalho = TrabalhoFactory(
        atividade=atividade, envio__atividade=atividade, aluno=aluno, identificacao="confirmada"
    )
    outro = AlunoFactory(turma=cenario["turma"])
    perfil_outro = PerfilApoioFactory(aluno=outro)
    assert PerfilApoio.history.filter(id=perfil.pk).exists()

    resp = auth_client.post(f"{URL}{consentimento.pk}/revogar/")

    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["ativo"] is False
    assert not tem_consentimento_ativo(aluno)
    assert not PerfilApoio.all_objects.filter(pk=perfil.pk).exists()
    assert not Relatorio.all_objects.filter(pk=relatorio.pk).exists()
    assert not Trabalho.all_objects.filter(pk=trabalho.pk).exists()
    assert not PerfilApoio.history.filter(id=perfil.pk).exists()
    assert not Relatorio.history.filter(id=relatorio.pk).exists()
    assert not Trabalho.history.filter(id=trabalho.pk).exists()
    assert PerfilApoio.objects.filter(pk=perfil_outro.pk).exists()
    assert Consentimento.objects.filter(pk=consentimento.pk).exists()


def test_revogar_duas_vezes_retorna_400(auth_client, cenario):
    consentimento = ConsentimentoFactory(aluno=cenario["aluno"])
    assert auth_client.post(f"{URL}{consentimento.pk}/revogar/").status_code == 200
    assert auth_client.post(f"{URL}{consentimento.pk}/revogar/").status_code == 400


def test_novo_consentimento_apos_revogacao(auth_client, cenario):
    consentimento = ConsentimentoFactory(aluno=cenario["aluno"])
    auth_client.post(f"{URL}{consentimento.pk}/revogar/")
    resp = auth_client.post(URL, {"aluno": cenario["aluno"].pk}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED


def test_listagem_so_mostra_consentimentos_proprios(auth_client, cenario):
    ConsentimentoFactory(aluno=cenario["aluno"])
    ConsentimentoFactory(aluno=AlunoFactory(turma=TurmaFactory(), consentimento=False))
    resp = auth_client.get(URL)
    assert resp.status_code == 200
    assert resp.data["count"] == 1


def test_envio_trabalho_de_aluno_sem_consentimento_descarta_analise(auth_client, user, cenario):
    from django.core.files.uploadedfile import SimpleUploadedFile

    atividade = AtividadeFactory(turma=cenario["turma"], criada_por=user)
    aluno = cenario["aluno"]
    resposta_ia = {
        "nome_lido": aluno.nome,
        "descricao": "descrição",
        "analise_pedagogica": {"pontos_fortes": ["x"]},
    }
    arquivo = SimpleUploadedFile("t.pdf", b"%PDF-1.4 %%EOF", content_type="application/pdf")
    with patch(
        "apps.pedagogico.services.trabalhos.analisar_trabalho_com_gemini",
        return_value=resposta_ia,
    ) as ia:
        resp = auth_client.post(
            f"/api/atividades/{atividade.pk}/trabalhos/",
            {"arquivos": [arquivo]},
            format="multipart",
        )
    assert resp.status_code == status.HTTP_201_CREATED
    # Nenhum nome da turma vai ao prompt da IA (B#83).
    assert "nomes_alunos_turma" not in ia.call_args.kwargs
    trabalho = Trabalho.objects.get()
    assert trabalho.identificacao == Trabalho.IdentificacaoChoices.SEM_CONSENTIMENTO
    assert trabalho.aluno is None
    assert trabalho.descricao_ia == ""
    assert not Relatorio.objects.exists()
