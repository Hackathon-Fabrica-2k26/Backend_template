import pytest
from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status

from apps.pedagogico.models import Trabalho
from apps.pedagogico.serializers import (
    AtividadeSerializer,
    AtividadeVariacaoSerializer,
    PerfilApoioSerializer,
    RelatorioSerializer,
    TrabalhoSerializer,
)

from .factories import (
    AlunoFactory,
    AtividadeFactory,
    AtividadeVariacaoFactory,
    EnvioTrabalhosFactory,
    PerfilApoioFactory,
    RelatorioFactory,
    TrabalhoFactory,
    TurmaFactory,
    VariacaoAlunoFactory,
)


@pytest.mark.django_db
def test_criar_relatorio_com_dados_json():
    dados_llm = {
        "profile_summary": "Resumo do perfil",
        "radar_metrics": {"foco_sustentado": 80},
    }
    relatorio = RelatorioFactory(dados=dados_llm)
    assert relatorio.pk is not None
    assert relatorio.dados == dados_llm
    assert str(relatorio) == f"Relatório #{relatorio.pk} (Aluno {relatorio.aluno_id})"


@pytest.mark.django_db
def test_criar_atividade_com_variacoes_e_relatorios():
    turma = TurmaFactory()
    aluno = AlunoFactory(turma=turma)
    atividade = AtividadeFactory(
        titulo="Missão Espacial",
        turma=turma,
    )
    v1 = AtividadeVariacaoFactory(atividade=atividade, numero=1, rotulo="prova_v1")
    VariacaoAlunoFactory(variacao=v1, aluno=aluno)
    rel = RelatorioFactory(aluno=aluno, atividade=atividade)

    assert atividade.variacoes.count() == 1
    assert list(v1.alunos) == [aluno]
    assert rel in atividade.relatorios.all()
    assert str(atividade) == "Missão Espacial"


@pytest.mark.django_db
def test_serializers_pedagogico():
    turma = TurmaFactory()
    aluno = AlunoFactory(turma=turma)
    ativ = AtividadeFactory(turma=turma)
    rel = RelatorioFactory(aluno=aluno, atividade=ativ, dados={"strengths": ["Memória visual"]})
    var = AtividadeVariacaoFactory(atividade=ativ, numero=1, rotulo="prova_v1")
    VariacaoAlunoFactory(variacao=var, aluno=aluno)
    perfil = PerfilApoioFactory(aluno=aluno)
    envio = EnvioTrabalhosFactory(atividade=ativ)
    trabalho = TrabalhoFactory(envio=envio, atividade=ativ, aluno=aluno, variacao=var)

    rel_data = RelatorioSerializer(rel).data
    assert rel_data["aluno"] == aluno.id
    assert rel_data["atividade"] == ativ.id
    assert rel_data["dados"] == {"strengths": ["Memória visual"]}

    ativ_data = AtividadeSerializer(ativ).data
    assert ativ_data["turma"] == turma.id
    assert ativ_data["titulo"] == ativ.titulo

    var_data = AtividadeVariacaoSerializer(var).data
    assert var_data["atividade"] == ativ.id
    assert var_data["alunos"] == [aluno.id]

    perfil_data = PerfilApoioSerializer(perfil).data
    assert perfil_data["aluno"] == aluno.id

    trab_data = TrabalhoSerializer(trabalho).data
    assert trab_data["atividade"] == ativ.id
    assert trab_data["aluno"] == aluno.id


@pytest.mark.django_db
def test_constraints_pedagogico():
    turma = TurmaFactory()
    aluno = AlunoFactory(turma=turma)
    atividade = AtividadeFactory(turma=turma)

    # 1. uq_variacao_atividade_numero
    v1 = AtividadeVariacaoFactory(atividade=atividade, numero=1)
    with pytest.raises(IntegrityError), transaction.atomic():
        AtividadeVariacaoFactory(atividade=atividade, numero=1)

    # 2. uq_variacao_aluno
    VariacaoAlunoFactory(variacao=v1, aluno=aluno)
    with pytest.raises(IntegrityError), transaction.atomic():
        VariacaoAlunoFactory(variacao=v1, aluno=aluno)

    # 3. uq_perfil_apoio_ativo_por_aluno
    PerfilApoioFactory(aluno=aluno, ativo=True)
    # Inativo é permitido:
    PerfilApoioFactory(aluno=aluno, ativo=False)
    # Segundo ativo viola a constraint:
    with pytest.raises(IntegrityError), transaction.atomic():
        PerfilApoioFactory(aluno=aluno, ativo=True)

    # 4. ck_trabalho_identificacao_exige_aluno
    envio = EnvioTrabalhosFactory(atividade=atividade)
    with pytest.raises(IntegrityError), transaction.atomic():
        TrabalhoFactory(
            envio=envio,
            atividade=atividade,
            aluno=None,
            identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
        )


@pytest.mark.django_db
def test_endpoints_variacoes_perfis_e_trabalhos_isolamento_lgpd(auth_client, user):
    minha_turma = TurmaFactory(professores=[user])
    meu_aluno = AlunoFactory(turma=minha_turma)
    minha_ativ = AtividadeFactory(turma=minha_turma, criada_por=user)

    outra_turma = TurmaFactory()
    outro_aluno = AlunoFactory(turma=outra_turma)
    outra_ativ = AtividadeFactory(turma=outra_turma)
    outra_var = AtividadeVariacaoFactory(atividade=outra_ativ, numero=1)
    outro_perfil = PerfilApoioFactory(aluno=outro_aluno)
    outro_trab = TrabalhoFactory(
        envio=EnvioTrabalhosFactory(atividade=outra_ativ),
        atividade=outra_ativ,
    )

    # Variações: cria com alunos da turma
    resp_var = auth_client.post(
        reverse("variacao-list"),
        {
            "atividade": minha_ativ.id,
            "numero": 1,
            "rotulo": "prova_v1",
            "eh_geral": True,
            "conteudo": "Conteúdo V1",
            "alunos": [meu_aluno.id],
        },
        format="json",
    )
    assert resp_var.status_code == status.HTTP_201_CREATED
    assert resp_var.json()["alunos"] == [meu_aluno.id]
    assert (
        auth_client.get(reverse("variacao-detail", args=[outra_var.id])).status_code
        == status.HTTP_404_NOT_FOUND
    )

    # Perfis de apoio: cria e valida unicidade ativa
    resp_perfil = auth_client.post(
        reverse("perfil-apoio-list"),
        {
            "aluno": meu_aluno.id,
            "necessidades": ["Apoio visual"],
            "estrategias": ["Pistas visuais"],
            "ativo": True,
        },
        format="json",
    )
    assert resp_perfil.status_code == status.HTTP_201_CREATED
    resp_perfil_dup = auth_client.post(
        reverse("perfil-apoio-list"),
        {"aluno": meu_aluno.id, "ativo": True},
        format="json",
    )
    assert resp_perfil_dup.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        auth_client.get(reverse("perfil-apoio-detail", args=[outro_perfil.id])).status_code
        == status.HTTP_404_NOT_FOUND
    )

    # Trabalhos: somente leitura e restrito às turmas do professor
    meu_trab = TrabalhoFactory(
        envio=EnvioTrabalhosFactory(atividade=minha_ativ, enviado_por=user),
        atividade=minha_ativ,
        aluno=meu_aluno,
        identificacao=Trabalho.IdentificacaoChoices.CONFIRMADA,
    )
    resp_trab = auth_client.get(reverse("trabalho-list"))
    assert resp_trab.status_code == status.HTTP_200_OK
    ids_trab = [t["id"] for t in resp_trab.json()["results"]]
    assert ids_trab == [meu_trab.id]
    assert (
        auth_client.get(reverse("trabalho-detail", args=[outro_trab.id])).status_code
        == status.HTTP_404_NOT_FOUND
    )
