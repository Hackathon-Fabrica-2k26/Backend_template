from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.pedagogico.models import Relatorio

User = get_user_model()

SENHA_TESTE = "senha-do-env-teste"
API_KEY_TESTE = "api-key-do-env-teste"


@pytest.fixture(name="rodar_seed")
def rodar_seed_fixture(db, monkeypatch):
    def rodar():
        monkeypatch.setenv("SEED_DEMO_PASSWORD", SENHA_TESTE)
        monkeypatch.setenv("SEED_DEMO_API_KEY", API_KEY_TESTE)
        saida = StringIO()
        call_command("seed_demo", stdout=saida)
        return saida.getvalue()

    return rodar


def test_seed_cria_dados_da_apresentacao(rodar_seed):
    rodar_seed()

    assert User.objects.filter(email="professor@demo.com").exists()
    assert Escola.objects.filter(nome="Escola Marsupi Demo").exists()
    assert Turma.objects.count() == 2
    assert Aluno.objects.count() == 6
    assert Responsavel.objects.count() == 6
    assert Relatorio.objects.count() == 2


def test_seed_e_idempotente(rodar_seed):
    rodar_seed()
    primeira_rodada = {
        "users": User.objects.count(),
        "escolas": Escola.objects.count(),
        "configs": Config.objects.count(),
        "turmas": Turma.objects.count(),
        "alunos": Aluno.objects.count(),
        "responsaveis": Responsavel.objects.count(),
        "meta_dados": MetaDados.objects.count(),
        "relatorios": Relatorio.objects.count(),
    }

    rodar_seed()
    segunda_rodada = {
        "users": User.objects.count(),
        "escolas": Escola.objects.count(),
        "configs": Config.objects.count(),
        "turmas": Turma.objects.count(),
        "alunos": Aluno.objects.count(),
        "responsaveis": Responsavel.objects.count(),
        "meta_dados": MetaDados.objects.count(),
        "relatorios": Relatorio.objects.count(),
    }

    assert primeira_rodada == segunda_rodada


def test_seed_professor_tem_senha_e_turmas(rodar_seed):
    rodar_seed()

    professor = User.objects.get(email="professor@demo.com")
    assert professor.check_password(SENHA_TESTE)
    assert professor.matricula == "DEMO0001"
    assert professor.escola.nome == "Escola Marsupi Demo"
    assert Turma.objects.filter(professores=professor).count() == 2


def test_seed_alunos_tem_responsavel_e_perfil_disc(rodar_seed):
    rodar_seed()

    alunos = Aluno.objects.all()
    assert alunos.count() == 6
    for aluno in alunos:
        assert aluno.responsavel is not None
        assert aluno.meta_dados is not None
        assert aluno.meta_dados.perfil_disc in {"D", "I", "S", "C"}
    assert {a["turma__nome"] for a in alunos.values("turma__nome")} == {"Turma A", "Turma B"}


def test_seed_relatorios_seguem_o_contrato(rodar_seed):
    rodar_seed()

    mascara = {
        "profile_summary",
        "radar_metrics",
        "strengths",
        "support_needs",
        "adapted_activities",
        "autonomy_coaching_tip",
    }
    radar = {
        "foco_sustentado",
        "raciocinio_visual",
        "interacao_social",
        "regulacao_sensorial",
        "coordenacao_fina",
    }
    relatorios = Relatorio.objects.all()
    assert relatorios.count() == 2
    for relatorio in relatorios:
        assert set(relatorio.dados) == mascara
        assert set(relatorio.dados["radar_metrics"]) == radar


def test_seed_escola_tem_config_com_placeholder(rodar_seed):
    rodar_seed()

    escola = Escola.objects.get(nome="Escola Marsupi Demo")
    assert escola.config is not None
    assert escola.config.modelo == "demo-model"
    assert escola.config.api_key == API_KEY_TESTE


@pytest.mark.django_db
def test_seed_sem_senha_fora_do_debug_aborta(monkeypatch):
    monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_DEMO_API_KEY", raising=False)

    with pytest.raises(CommandError) as erro:
        call_command("seed_demo")

    assert "Defina SEED_DEMO_PASSWORD para rodar o seed fora do DEBUG." in str(erro.value)
    assert not User.objects.filter(email="professor@demo.com").exists()
    assert not Escola.objects.filter(nome="Escola Marsupi Demo").exists()


@pytest.mark.django_db
def test_seed_sem_api_key_fora_do_debug_aborta(monkeypatch):
    monkeypatch.setenv("SEED_DEMO_PASSWORD", SENHA_TESTE)
    monkeypatch.delenv("SEED_DEMO_API_KEY", raising=False)

    with pytest.raises(CommandError) as erro:
        call_command("seed_demo")

    assert "Defina SEED_DEMO_API_KEY para rodar o seed fora do DEBUG." in str(erro.value)


@override_settings(DEBUG=True)
@pytest.mark.django_db
def test_seed_com_debug_usa_padroes(monkeypatch):
    monkeypatch.delenv("SEED_DEMO_PASSWORD", raising=False)
    monkeypatch.delenv("SEED_DEMO_API_KEY", raising=False)

    call_command("seed_demo", stdout=StringIO())

    professor = User.objects.get(email="professor@demo.com")
    assert professor.check_password("demo-senha-123")
    assert Escola.objects.get(nome="Escola Marsupi Demo").config.api_key == (
        "demo-api-key-troque-no-admin"
    )


@pytest.mark.django_db
def test_seed_nao_sobrescreve_config_existente(monkeypatch):
    monkeypatch.setenv("SEED_DEMO_PASSWORD", SENHA_TESTE)
    monkeypatch.setenv("SEED_DEMO_API_KEY", API_KEY_TESTE)

    config = Config.objects.create(api_key="api-key-real-config", modelo="modelo-real")
    escola = Escola.objects.create(
        nome="Escola Marsupi Demo", endereco="Rua da Demo, 101", config=config
    )

    call_command("seed_demo", stdout=StringIO())

    escola.refresh_from_db()
    assert escola.config_id == config.id
    assert escola.config.api_key == "api-key-real-config"
    assert Config.objects.count() == 1
