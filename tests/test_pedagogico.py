import pytest

from apps.pedagogico.serializers import AtividadeSerializer, RelatorioSerializer

from .factories import AlunoFactory, AtividadeFactory, RelatorioFactory


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
def test_criar_atividade_com_relatorios_m2m():
    aluno = AlunoFactory()
    rel1 = RelatorioFactory(aluno=aluno)
    rel2 = RelatorioFactory(aluno=aluno)
    atividade = AtividadeFactory(
        nome="Missão Espacial",
        tipo="Motricidade",
        aluno=aluno,
        relatorios=[rel1, rel2],
    )
    assert atividade.relatorios.count() == 2
    assert rel1 in atividade.relatorios.all()
    assert atividade in rel1.atividades.all()
    assert str(atividade) == "Missão Espacial"


@pytest.mark.django_db
def test_serializers_pedagogico():
    aluno = AlunoFactory()
    rel = RelatorioFactory(aluno=aluno, dados={"strengths": ["Memória visual"]})
    ativ = AtividadeFactory(aluno=aluno, relatorios=[rel])

    rel_data = RelatorioSerializer(rel).data
    assert rel_data["aluno"] == aluno.id
    assert rel_data["dados"] == {"strengths": ["Memória visual"]}

    ativ_data = AtividadeSerializer(ativ).data
    assert ativ_data["aluno"] == aluno.id
    assert ativ_data["relatorios"] == [rel.id]
