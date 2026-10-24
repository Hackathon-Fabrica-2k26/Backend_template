import pytest

from apps.alunos.models import Aluno
from apps.escolas.models import Turma

from .factories import (
    AlunoFactory,
    ConfigFactory,
    EscolaFactory,
    TurmaFactory,
    UserFactory,
)

URL_TURMAS = "/api/turmas/"
URL_ESCOLAS = "/api/escolas/"
URL_CONFIGS = "/api/configs/"

pytestmark = pytest.mark.django_db


def test_sem_token_retorna_401(api_client):
    assert api_client.get(URL_TURMAS).status_code == 401
    assert api_client.get(URL_ESCOLAS).status_code == 401
    assert api_client.get(URL_CONFIGS).status_code == 401


def test_turma_de_outro_professor_retorna_404(auth_client, user):
    outro_professor = UserFactory()
    turma_outro = TurmaFactory(professores=[outro_professor])

    resp = auth_client.get(f"{URL_TURMAS}{turma_outro.id}/")
    assert resp.status_code == 404


def test_professor_so_ve_suas_turmas(auth_client, user):
    outro_professor = UserFactory()
    turma_minha = TurmaFactory(nome="Minha Turma", professores=[user])
    TurmaFactory(nome="Outra Turma", professores=[outro_professor])

    resp = auth_client.get(URL_TURMAS)
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["count"] == 1
    assert dados["results"][0]["id"] == turma_minha.id
    assert dados["results"][0]["nome"] == "Minha Turma"


def test_filtro_turmas_por_escola(auth_client, user):
    escola1 = EscolaFactory(nome="Escola Um")
    escola2 = EscolaFactory(nome="Escola Dois")
    turma1 = TurmaFactory(escola=escola1, professores=[user])
    TurmaFactory(escola=escola2, professores=[user])

    resp = auth_client.get(URL_TURMAS, {"escola": escola1.id})
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["results"]]
    assert ids == [turma1.id]


def test_busca_turmas_por_nome(auth_client, user):
    TurmaFactory(nome="Matemática 101", professores=[user])
    TurmaFactory(nome="História 202", professores=[user])

    resp = auth_client.get(URL_TURMAS, {"search": "Matemática"})
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) == 1
    assert results[0]["nome"] == "Matemática 101"


def test_validacao_turma_obrigatoria_retorna_400(auth_client):
    resp = auth_client.post(URL_TURMAS, {})
    assert resp.status_code == 400
    erros = resp.json()
    assert "nome" in erros
    assert "escola" in erros


def test_criacao_turma_vincula_professor_logado(auth_client, user):
    config = ConfigFactory()
    escola = EscolaFactory(config=config)
    resp = auth_client.post(URL_TURMAS, {"nome": "Nova Turma", "escola": escola.id})
    assert resp.status_code == 201

    turma_id = resp.json()["id"]
    turma = Turma.objects.get(id=turma_id)
    assert user in turma.professores.all()


def test_turno_invalido_retorna_400(auth_client):
    escola = EscolaFactory()
    resp = auth_client.post(
        URL_TURMAS,
        {"nome": "Turma X", "escola": escola.id, "turno": "madrugada"},
    )
    assert resp.status_code == 400
    assert "turno" in resp.json()


def test_turno_e_total_estudantes_conta_apenas_alunos_ativos(auth_client, user):
    outro_professor = UserFactory()
    turma = TurmaFactory(nome="1º Ano A", turno="tarde", professores=[user])
    turma_outro = TurmaFactory(nome="2º Ano B", turno="manha", professores=[outro_professor])

    AlunoFactory(nome="Ativo 1", turma=turma)
    AlunoFactory(nome="Ativo 2", turma=turma)
    AlunoFactory(nome="Inativo", turma=turma, ativo=False)
    excluido = AlunoFactory(nome="Excluído", turma=turma)
    excluido.delete()
    AlunoFactory(nome="Aluno de Outra Turma", turma=turma_outro)

    resp = auth_client.get(URL_TURMAS)
    assert resp.status_code == 200
    dados = resp.json()
    assert dados["count"] == 1
    item = dados["results"][0]
    assert item["id"] == turma.id
    assert item["turno"] == "tarde"
    assert item["turno_display"] == "Tarde"
    assert item["total_estudantes"] == 2


def test_turma_ano_letivo_default_e_filtro(auth_client, user):
    from datetime import date

    turma_2025 = TurmaFactory(nome="Turma 2025", ano_letivo=2025, professores=[user])
    turma_atual = TurmaFactory(nome="Turma Atual", professores=[user])

    assert turma_atual.ano_letivo == date.today().year

    resp = auth_client.get(URL_TURMAS, {"ano_letivo": 2025})
    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["results"]]
    assert ids == [turma_2025.id]
    assert resp.json()["results"][0]["ano_letivo"] == 2025


def test_api_key_nao_volta_na_resposta(auth_client, user):
    config = ConfigFactory(api_key="chave-super-secreta", modelo="gemini-1.5-pro")
    escola = EscolaFactory(config=config)
    TurmaFactory(escola=escola, professores=[user])

    # Leitura na lista
    resp_list = auth_client.get(URL_CONFIGS)
    assert resp_list.status_code == 200
    item = resp_list.json()["results"][0]
    assert "api_key" not in item
    assert item["modelo"] == "gemini-1.5-pro"

    # Leitura no detalhe
    resp_detail = auth_client.get(f"{URL_CONFIGS}{config.id}/")
    assert resp_detail.status_code == 200
    assert "api_key" not in resp_detail.json()

    # Criação de config
    resp_create = auth_client.post(
        URL_CONFIGS,
        {
            "api_key": "outra-chave-secreta",
            "modelo": "gpt-4o",
            "campos_form": {"campo": "valor"},
        },
        format="json",
    )
    assert resp_create.status_code == 201
    assert "api_key" not in resp_create.json()


def test_escolas_filtradas_por_professor(auth_client, user):
    outro_professor = UserFactory()
    escola_minha = EscolaFactory(nome="Escola Minha")
    escola_outra = EscolaFactory(nome="Escola Outra")

    TurmaFactory(escola=escola_minha, professores=[user])
    TurmaFactory(escola=escola_outra, professores=[outro_professor])

    resp = auth_client.get(URL_ESCOLAS)
    assert resp.status_code == 200
    ids = [e["id"] for e in resp.json()["results"]]
    assert ids == [escola_minha.id]

    assert auth_client.get(f"{URL_ESCOLAS}{escola_outra.id}/").status_code == 404


def test_configs_filtradas_por_professor(auth_client, user):
    outro_professor = UserFactory()
    config_minha = ConfigFactory(modelo="modelo-minha")
    config_outra = ConfigFactory(modelo="modelo-outra")

    escola_minha = EscolaFactory(config=config_minha)
    escola_outra = EscolaFactory(config=config_outra)

    TurmaFactory(escola=escola_minha, professores=[user])
    TurmaFactory(escola=escola_outra, professores=[outro_professor])

    resp = auth_client.get(URL_CONFIGS)
    assert resp.status_code == 200
    ids = [c["id"] for c in resp.json()["results"]]
    assert ids == [config_minha.id]

    assert auth_client.get(f"{URL_CONFIGS}{config_outra.id}/").status_code == 404


def test_exclusao_logica_e_historico(user):
    config = ConfigFactory()
    escola = EscolaFactory(config=config)
    turma = TurmaFactory(escola=escola, professores=[user])

    turma.delete()
    assert turma.history.first().history_change_reason == "Exclusão lógica"
    assert Turma.all_objects.filter(pk=turma.pk).exists()
    assert not Turma.objects.filter(pk=turma.pk).exists()

    turma.undelete()
    assert turma.history.first().history_change_reason == "Restauração"
    assert Turma.objects.filter(pk=turma.pk).exists()


def test_rotas_no_schema(client):
    resp = client.get("/api/schema/", {"format": "json"})
    assert resp.status_code == 200
    paths = resp.json()["paths"]
    assert "/api/configs/" in paths
    assert "/api/escolas/" in paths
    assert "/api/turmas/" in paths


def test_criar_turma_com_3_alunos_usa_escola_do_professor_e_retorna_total_estudantes(
    auth_client, user
):
    escola = EscolaFactory(nome="Escola do Professor")
    user.escola = escola
    user.save()

    payload = {
        "nome": "1º Ano A",
        "ano_letivo": 2026,
        "turno": "manha",
        "alunos": ["Alice Silva", "Bruno Costa", "Carla Dias"],
    }
    resp = auth_client.post(URL_TURMAS, payload, format="json")
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["nome"] == "1º Ano A"
    assert corpo["ano_letivo"] == 2026
    assert corpo["turno"] == "manha"
    assert corpo["turno_display"] == "Manhã"
    assert corpo["escola"] == escola.id
    assert corpo["total_estudantes"] == 3
    assert user.id in corpo["professores"]

    turma = Turma.objects.get(pk=corpo["id"])
    assert list(turma.alunos.order_by("id").values_list("nome", flat=True)) == [
        "Alice Silva",
        "Bruno Costa",
        "Carla Dias",
    ]


def test_criar_turma_ignora_nomes_vazios_e_duplicados_sem_diferenciar_maiusculas_e_espacos(
    auth_client, user
):
    user.escola = EscolaFactory()
    user.save()

    payload = {
        "nome": "2º Ano B",
        "ano_letivo": 2026,
        "turno": "tarde",
        "alunos": [
            "  Alice   Silva  ",
            "",
            "   ",
            "ALICE silva",
            "AliceSilva",
            "Bruno  Costa",
            "bruno costa ",
        ],
    }
    resp = auth_client.post(URL_TURMAS, payload, format="json")
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["total_estudantes"] == 2

    turma = Turma.objects.get(pk=corpo["id"])
    assert list(turma.alunos.order_by("id").values_list("nome", flat=True)) == [
        "Alice Silva",
        "Bruno Costa",
    ]


def test_criar_turma_faz_rollback_se_um_nome_for_invalido_ou_exceder_limite(auth_client, user):
    user.escola = EscolaFactory()
    user.save()

    # Nome acima de 120 caracteres após o primeiro aluno válido -> rollback completo
    resp = auth_client.post(
        URL_TURMAS,
        {
            "nome": "Turma Rollback",
            "ano_letivo": 2026,
            "turno": "manha",
            "alunos": ["Aluno Válido", "X" * 121],
        },
        format="json",
    )
    assert resp.status_code == 400
    assert "alunos" in resp.json()
    assert not Turma.objects.filter(nome="Turma Rollback").exists()
    assert Aluno.objects.count() == 0

    # Mais de 60 nomes -> 400 e nada criado
    resp_limite = auth_client.post(
        URL_TURMAS,
        {
            "nome": "Turma Limite",
            "ano_letivo": 2026,
            "turno": "manha",
            "alunos": [f"Aluno {i}" for i in range(61)],
        },
        format="json",
    )
    assert resp_limite.status_code == 400
    assert "alunos" in resp_limite.json()
    assert not Turma.objects.filter(nome="Turma Limite").exists()
    assert Aluno.objects.count() == 0


def test_criar_turma_sem_alunos_continua_funcionando(auth_client, user):
    user.escola = EscolaFactory()
    user.save()

    resp = auth_client.post(
        URL_TURMAS,
        {"nome": "Turma Sem Alunos", "ano_letivo": 2026, "turno": "noite"},
        format="json",
    )
    assert resp.status_code == 201
    corpo = resp.json()
    assert corpo["total_estudantes"] == 0
    assert Aluno.objects.count() == 0


def test_criar_turma_com_alunos_isolamento_por_professor(api_client, auth_client, user):
    user.escola = EscolaFactory()
    user.save()

    resp = auth_client.post(
        URL_TURMAS,
        {
            "nome": "Turma Privada",
            "ano_letivo": 2026,
            "turno": "manha",
            "alunos": ["Estudante 1", "Estudante 2"],
        },
        format="json",
    )
    assert resp.status_code == 201
    turma_id = resp.json()["id"]

    outro_professor = UserFactory()
    api_client.force_authenticate(user=outro_professor)
    assert api_client.get(f"{URL_TURMAS}{turma_id}/").status_code == 404
    resp_alunos = api_client.get("/api/alunos/", {"turma": turma_id})
    assert resp_alunos.status_code == 200
    assert resp_alunos.json()["count"] == 0
