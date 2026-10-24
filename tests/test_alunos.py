from django.urls import reverse
from rest_framework import status

from .factories import (
    AlunoFactory,
    MetaDadosFactory,
    RelatorioFactory,
    ResponsavelFactory,
    TurmaFactory,
)

LIST_URL = reverse("aluno-list")


def _cria_turmas_com_aluno(professor):
    """Turma do professor com 1 aluno; outra turma sem vínculo com o professor."""
    turma_do_professor = TurmaFactory(professores=[professor])
    aluno = AlunoFactory(turma=turma_do_professor)
    outra_turma = TurmaFactory()
    outro_aluno = AlunoFactory(turma=outra_turma)
    return turma_do_professor, aluno, outra_turma, outro_aluno


def test_aluno_list_exige_autenticacao(api_client, db):
    response = api_client.get(LIST_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_aluno_detail_de_turma_alheia_retorna_404(auth_client, db, user):
    _, _, _, outro_aluno = _cria_turmas_com_aluno(user)
    url = reverse("aluno-detail", args=[outro_aluno.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # LGPD: dados de aluno de outra turma nunca são expostos ao professor.
    assert response.json().get("nome") is None


def test_aluno_sem_turma_nao_e_visto_por_outro_usuario(auth_client, db, user):
    aluno = AlunoFactory(turma=None)
    url = reverse("aluno-detail", args=[aluno.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_aluno_list_filtra_por_turma(auth_client, db, user):
    turma_do_professor, aluno, _, _ = _cria_turmas_com_aluno(user)
    response = auth_client.get(LIST_URL, {"turma": turma_do_professor.pk})
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [aluno.pk]


def test_aluno_list_nao_retorna_turmas_alheias(auth_client, db, user):
    _, _, _, outro_aluno = _cria_turmas_com_aluno(user)
    response = auth_client.get(LIST_URL)
    ids = [item["id"] for item in response.data["results"]]
    assert outro_aluno.pk not in ids


def test_aluno_busca_por_nome(auth_client, db, user):
    turma = TurmaFactory(professores=[user])
    AlunoFactory(turma=turma, nome="Maria Souza")
    AlunoFactory(turma=turma, nome="João Lima")
    response = auth_client.get(LIST_URL, {"search": "Maria"})
    nomes = [item["nome"] for item in response.data["results"]]
    assert nomes == ["Maria Souza"]


def test_aluno_create_sem_campos_retorna_400(auth_client, db):
    response = auth_client.post(LIST_URL, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_aluno_create_com_turma_inexistente_retorna_400(auth_client, db):
    formulario = {"nome": "Novo Aluno", "turma": 99999}
    response = auth_client.post(LIST_URL, formulario)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_aluno_create_sem_turma_retorna_400(auth_client, db):
    response = auth_client.post(LIST_URL, {"nome": "Sem Turma"}, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "turma" in response.json()


def test_aluno_create_turma_de_outro_professor_retorna_400(auth_client, db, user):
    turma_alheia = TurmaFactory()
    formulario = {"nome": "Novo Aluno", "turma": turma_alheia.pk}
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "turma" in response.json()


def test_aluno_create_valido(auth_client, db, user):
    turma = TurmaFactory(professores=[user])
    formulario = {"nome": "Novo Aluno", "turma": turma.pk}
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nome"] == "Novo Aluno"


def test_responsavel_list_exige_autenticacao(api_client, db):
    response = api_client.get(reverse("responsavel-list"))
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_responsavel_restrito_a_turma_do_professor(auth_client, db, user):
    turma = TurmaFactory(professores=[user])
    aluno = AlunoFactory(turma=turma)
    meu_responsavel = ResponsavelFactory()
    aluno.responsavel = meu_responsavel
    aluno.save()

    outro_aluno = AlunoFactory()
    responsavel_alheio = ResponsavelFactory()
    outro_aluno.responsavel = responsavel_alheio
    outro_aluno.save()

    response = auth_client.get(reverse("responsavel-list"))
    ids = [item["id"] for item in response.data["results"]]
    assert meu_responsavel.pk in ids
    assert responsavel_alheio.pk not in ids

    response = auth_client.get(reverse("responsavel-detail", args=[responsavel_alheio.pk]))
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # LGPD: CPF de responsável fora do escopo do professor nunca é exposto.
    assert response.json().get("cpf") is None


def test_responsavel_create_valido(auth_client, db):
    formulario = {
        "nome": "Responsável Teste",
        "email": "resp@example.com",
        "telefone": "11987654321",
        "cpf": "12345678900",
        "endereco": "Rua X",
    }
    response = auth_client.post(reverse("responsavel-list"), formulario)
    assert response.status_code == status.HTTP_201_CREATED


def test_responsavel_create_sem_nome_retorna_400(auth_client, db):
    response = auth_client.post(reverse("responsavel-list"), {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_meta_dados_restrito_a_turma_do_professor(auth_client, db, user):
    turma_do_professor = TurmaFactory(professores=[user])
    meus_meta = MetaDadosFactory()
    AlunoFactory(turma=turma_do_professor, meta_dados=meus_meta)

    turma_alheia = TurmaFactory()
    meta_alheio = MetaDadosFactory()
    AlunoFactory(turma=turma_alheia, meta_dados=meta_alheio)

    response = auth_client.get(reverse("meta-dados-list"))
    ids = [item["id"] for item in response.data["results"]]
    assert meus_meta.pk in ids
    assert meta_alheio.pk not in ids

    response = auth_client.get(reverse("meta-dados-detail", args=[meta_alheio.pk]))
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_meta_dados_create_valido(auth_client, db):
    formulario = {"perfil_disc": "D", "caracteristicas": {"energia": "alta"}}
    response = auth_client.post(reverse("meta-dados-list"), formulario, format="json")
    assert response.status_code == status.HTTP_201_CREATED


def test_meta_dados_create_perfil_invalido_retorna_400(auth_client, db):
    formulario = {"perfil_disc": "X"}
    response = auth_client.post(reverse("meta-dados-list"), formulario)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_aluno_list_retorna_resumo_com_contagens_e_ignora_soft_deleted(auth_client, db, user):
    turma = TurmaFactory(professores=[user])
    aluno_com_relatorios = AlunoFactory(turma=turma, nome="Aluno com Relatórios")
    aluno_sem_relatorios = AlunoFactory(turma=turma, nome="Aluno sem Relatórios")

    RelatorioFactory(aluno=aluno_com_relatorios)
    RelatorioFactory(aluno=aluno_com_relatorios)
    relatorio_deletado = RelatorioFactory(aluno=aluno_com_relatorios)
    relatorio_deletado.delete()

    response = auth_client.get(LIST_URL, {"turma": turma.pk})
    assert response.status_code == status.HTTP_200_OK

    dados_alunos = {item["id"]: item for item in response.data["results"]}
    assert aluno_com_relatorios.pk in dados_alunos
    assert aluno_sem_relatorios.pk in dados_alunos

    resumo_com = dados_alunos[aluno_com_relatorios.pk]["resumo"]
    assert resumo_com == {
        "relatorios": 2,
        "trabalhos": 0,
        "observacoes_pendentes": 0,
    }

    resumo_sem = dados_alunos[aluno_sem_relatorios.pk]["resumo"]
    assert resumo_sem == {
        "relatorios": 0,
        "trabalhos": 0,
        "observacoes_pendentes": 0,
    }


def test_aluno_detail_retorna_resumo(auth_client, db, user):
    turma = TurmaFactory(professores=[user])
    aluno = AlunoFactory(turma=turma)
    RelatorioFactory(aluno=aluno)

    url = reverse("aluno-detail", args=[aluno.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert response.data["resumo"] == {
        "relatorios": 1,
        "trabalhos": 0,
        "observacoes_pendentes": 0,
    }


def test_aluno_list_resumo_sem_n_plus_one(auth_client, db, user, django_assert_num_queries):
    turma = TurmaFactory(professores=[user])
    alunos = [AlunoFactory(turma=turma) for _ in range(5)]
    for aluno in alunos:
        RelatorioFactory(aluno=aluno)
        RelatorioFactory(aluno=aluno)

    with django_assert_num_queries(3):
        response = auth_client.get(LIST_URL, {"turma": turma.pk})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 5
        for item in response.data["results"]:
            assert item["resumo"]["relatorios"] == 2
