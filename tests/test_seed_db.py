from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from apps.alunos.models import Aluno, MetaDados, Responsavel
from apps.escolas.models import Config, Escola, Turma
from apps.items.models import Item
from apps.pedagogico.models import Atividade, Relatorio

User = get_user_model()


@pytest.fixture(name="executar_seed")
def executar_seed_fixture(db):
    def _rodar(*args, **kwargs):
        saida = StringIO()
        call_command("seed_db", *args, stdout=saida, **kwargs)
        return saida.getvalue()

    return _rodar


def test_seed_db_popula_entidades_completas(executar_seed):
    saida = executar_seed()
    assert "✓ Database seeding finalizado com sucesso!" in saida

    # Superusuário
    admin = User.objects.get(matricula="ADMIN0001")
    assert admin.email == "admin@exemplo.com"
    assert admin.is_superuser is True
    assert admin.is_staff is True
    assert admin.check_password("admin123") is True

    # Config & Escolas
    assert Config.objects.filter(modelo="gemini-2.5-flash").exists()
    assert Escola.objects.count() == 2
    for escola in Escola.objects.all():
        assert escola.config is not None

    # Professores / Usuários comuns
    professores = User.objects.filter(matricula__startswith="PROF")
    assert professores.count() == 5
    for prof in professores:
        assert prof.check_password("senha123") is True
        assert prof.escola is not None
        assert prof.is_staff is False
        assert prof.is_superuser is False

    # Turmas
    turmas = Turma.objects.all()
    assert turmas.count() == 4
    for turma in turmas:
        assert turma.escola is not None
        assert turma.turno in Turma.TurnoChoices.values
        assert turma.professores.exists()

    # Responsáveis e Alunos
    assert Responsavel.objects.count() == 16
    assert Aluno.objects.count() == 16
    for aluno in Aluno.objects.all():
        assert aluno.turma is not None
        assert aluno.responsavel is not None
        assert aluno.meta_dados is not None
        assert aluno.meta_dados.perfil_disc in {"D", "I", "S", "C"}
        assert "estilo" in aluno.meta_dados.caracteristicas

    # Relatórios e Atividades
    assert Relatorio.objects.count() == 16
    for relatorio in Relatorio.objects.all():
        dados = relatorio.dados
        assert "profile_summary" in dados
        assert "radar_metrics" in dados
        assert "foco_sustentado" in dados["radar_metrics"]
        assert "strengths" in dados
        assert "support_needs" in dados
        assert "adapted_activities" in dados
        assert "autonomy_coaching_tip" in dados

    assert Atividade.objects.count() == 16
    for ativ in Atividade.objects.all():
        assert ativ.aluno is not None
        assert ativ.relatorios.exists()

    # Itens mockados
    itens = Item.objects.all()
    assert itens.count() == 5
    for item in itens:
        assert item.owner in professores


def test_seed_db_idempotencia(executar_seed):
    executar_seed()

    snapshot_1 = {
        "users": User.objects.count(),
        "configs": Config.objects.count(),
        "escolas": Escola.objects.count(),
        "turmas": Turma.objects.count(),
        "responsaveis": Responsavel.objects.count(),
        "alunos": Aluno.objects.count(),
        "meta_dados": MetaDados.objects.count(),
        "relatorios": Relatorio.objects.count(),
        "atividades": Atividade.objects.count(),
        "itens": Item.objects.count(),
    }

    # Segunda execução sem --clear
    saida_segunda = executar_seed()
    assert "✓ Database seeding finalizado com sucesso!" in saida_segunda

    snapshot_2 = {
        "users": User.objects.count(),
        "configs": Config.objects.count(),
        "escolas": Escola.objects.count(),
        "turmas": Turma.objects.count(),
        "responsaveis": Responsavel.objects.count(),
        "alunos": Aluno.objects.count(),
        "meta_dados": MetaDados.objects.count(),
        "relatorios": Relatorio.objects.count(),
        "atividades": Atividade.objects.count(),
        "itens": Item.objects.count(),
    }

    assert snapshot_1 == snapshot_2


def test_seed_db_flag_clear(executar_seed):
    executar_seed()
    assert Aluno.objects.count() > 0

    saida_clear = executar_seed("--clear")
    assert "Limpando dados antigos com exclusão permanente..." in saida_clear
    assert "✓ Database seeding finalizado com sucesso!" in saida_clear

    # Confirma que recriou após a limpeza
    assert User.objects.filter(matricula="ADMIN0001").exists()
    assert Escola.objects.count() == 2
    assert Aluno.objects.count() == 16


def test_seed_db_parametros_customizados(executar_seed):
    saida = executar_seed(
        "--clear",
        "--users",
        "3",
        "--escolas",
        "1",
        "--turmas-por-escola",
        "1",
        "--alunos-por-turma",
        "2",
    )
    assert "✓ Database seeding finalizado com sucesso!" in saida

    assert Escola.objects.count() == 1
    assert Turma.objects.count() == 1
    assert User.objects.filter(matricula__startswith="PROF").count() == 3
    assert Aluno.objects.count() == 2
    assert Responsavel.objects.count() == 2
    assert Relatorio.objects.count() == 2


def test_seed_db_variaveis_de_ambiente(executar_seed, monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_EMAIL", "customadmin@dominio.com")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "SuperSenhaAdmin999")
    monkeypatch.setenv("SEED_USER_PASSWORD", "SuperSenhaProf888")

    executar_seed("--clear", "--users", "1")

    admin = User.objects.get(matricula="ADMIN0001")
    assert admin.email == "customadmin@dominio.com"
    assert admin.check_password("SuperSenhaAdmin999") is True

    prof = User.objects.get(matricula="PROF0001")
    assert prof.check_password("SuperSenhaProf888") is True
