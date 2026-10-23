from django.urls import reverse
from rest_framework import status

from .factories import AlunoFactory, AtividadeFactory, TurmaFactory

LIST_URL = reverse("atividade-list")


def _cria_turmas_com_aluno(professor):
    """Turma do professor com 1 aluno; outra turma sem vínculo com o professor."""
    turma_do_professor = TurmaFactory(professores=[professor])
    aluno = AlunoFactory(turma=turma_do_professor)
    outra_turma = TurmaFactory()
    outro_aluno = AlunoFactory(turma=outra_turma)
    return aluno, outro_aluno


def test_atividade_list_exige_autenticacao(api_client, db):
    response = api_client.get(LIST_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_atividade_detail_de_turma_alheia_retorna_404(auth_client, db, user):
    _, outro_aluno = _cria_turmas_com_aluno(user)
    atividade = AtividadeFactory(aluno=outro_aluno)
    url = reverse("atividade-detail", args=[atividade.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # LGPD: dados de aluno de outra turma nunca são expostos ao professor.
    assert response.json().get("nome") is None


def test_atividade_sem_turma_nao_e_visto_por_professor(auth_client, db):
    aluno = AlunoFactory(turma=None)
    atividade = AtividadeFactory(aluno=aluno)
    url = reverse("atividade-detail", args=[atividade.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_atividade_list_filtra_por_aluno(auth_client, db, user):
    aluno, outro_aluno = _cria_turmas_com_aluno(user)
    minha = AtividadeFactory(aluno=aluno, nome="Minha atividade")
    AtividadeFactory(aluno=outro_aluno, nome="Atividade alheia")
    response = auth_client.get(LIST_URL, {"aluno": aluno.pk})
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [minha.pk]


def test_atividade_list_nao_retorna_turmas_alheias(auth_client, db, user):
    _, outro_aluno = _cria_turmas_com_aluno(user)
    alheia = AtividadeFactory(aluno=outro_aluno)
    response = auth_client.get(LIST_URL)
    ids = [item["id"] for item in response.data["results"]]
    assert alheia.pk not in ids


def test_atividade_busca_por_nome(auth_client, db, user):
    aluno, _ = _cria_turmas_com_aluno(user)
    AtividadeFactory(aluno=aluno, nome="Leitura dirigida")
    AtividadeFactory(aluno=aluno, nome="Ditado")
    response = auth_client.get(LIST_URL, {"search": "Leitura"})
    nomes = [item["nome"] for item in response.data["results"]]
    assert nomes == ["Leitura dirigida"]


def test_atividade_create_sem_campos_retorna_400(auth_client, db):
    response = auth_client.post(LIST_URL, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_atividade_create_com_aluno_inexistente_retorna_400(auth_client, db):
    formulario = {"nome": "Nova Atividade", "tipo": "leitura", "aluno": 99999}
    response = auth_client.post(LIST_URL, formulario)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_atividade_create_aluno_de_turma_alheia_retorna_400(auth_client, db, user):
    _, outro_aluno = _cria_turmas_com_aluno(user)
    formulario = {"nome": "Nova Atividade", "tipo": "leitura", "aluno": outro_aluno.pk}
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "aluno" in response.json()


def test_atividade_create_valido(auth_client, db, user):
    aluno, _ = _cria_turmas_com_aluno(user)
    formulario = {"nome": "Nova Atividade", "tipo": "leitura", "aluno": aluno.pk}
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["nome"] == "Nova Atividade"
    assert response.data["aluno"] == aluno.pk
