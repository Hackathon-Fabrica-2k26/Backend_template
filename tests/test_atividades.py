from django.urls import reverse
from rest_framework import status

from .factories import AtividadeFactory, TurmaFactory

LIST_URL = reverse("atividade-list")


def _cria_turmas(professor):
    """Turma do professor e outra turma sem vínculo com o professor."""
    turma_do_professor = TurmaFactory(professores=[professor])
    outra_turma = TurmaFactory()
    return turma_do_professor, outra_turma


def test_atividade_list_exige_autenticacao(api_client, db):
    response = api_client.get(LIST_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_atividade_detail_de_turma_alheia_retorna_404(auth_client, db, user):
    _, outra_turma = _cria_turmas(user)
    atividade = AtividadeFactory(turma=outra_turma)
    url = reverse("atividade-detail", args=[atividade.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json().get("titulo") is None


def test_atividade_list_filtra_por_turma(auth_client, db, user):
    turma, outra_turma = _cria_turmas(user)
    minha = AtividadeFactory(turma=turma, titulo="Minha atividade")
    AtividadeFactory(turma=outra_turma, titulo="Atividade alheia")
    response = auth_client.get(LIST_URL, {"turma": turma.pk})
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [minha.pk]


def test_atividade_list_nao_retorna_turmas_alheias(auth_client, db, user):
    _, outra_turma = _cria_turmas(user)
    alheia = AtividadeFactory(turma=outra_turma)
    response = auth_client.get(LIST_URL)
    ids = [item["id"] for item in response.data["results"]]
    assert alheia.pk not in ids


def test_atividade_busca_por_titulo(auth_client, db, user):
    turma, _ = _cria_turmas(user)
    AtividadeFactory(turma=turma, titulo="Leitura dirigida")
    AtividadeFactory(turma=turma, titulo="Ditado")
    response = auth_client.get(LIST_URL, {"search": "Leitura"})
    titulos = [item["titulo"] for item in response.data["results"]]
    assert titulos == ["Leitura dirigida"]


def test_atividade_create_sem_campos_retorna_400(auth_client, db):
    response = auth_client.post(LIST_URL, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_atividade_create_com_turma_inexistente_retorna_400(auth_client, db):
    formulario = {
        "titulo": "Nova Atividade",
        "texto_original": "Conteúdo da atividade",
        "turma": 99999,
    }
    response = auth_client.post(LIST_URL, formulario)
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_atividade_create_turma_alheia_retorna_400(auth_client, db, user):
    _, outra_turma = _cria_turmas(user)
    formulario = {
        "titulo": "Nova Atividade",
        "texto_original": "Conteúdo da atividade",
        "turma": outra_turma.pk,
    }
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "turma" in response.json()


def test_atividade_create_valido(auth_client, db, user):
    turma, _ = _cria_turmas(user)
    formulario = {
        "titulo": "Nova Atividade",
        "origem": "pdf",
        "texto_original": "Texto extraído do PDF",
        "objetivo": "Trabalhar interpretação",
        "turma": turma.pk,
    }
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["titulo"] == "Nova Atividade"
    assert response.data["turma"] == turma.pk
    assert response.data["criada_por"] == user.pk
    assert response.data["status"] == "rascunho"
