from django.urls import reverse
from rest_framework import status

from apps.pedagogico.services import DISCLAIMER

from .factories import AlunoFactory, AtividadeFactory, RelatorioFactory, TurmaFactory

LIST_URL = reverse("relatorio-list")


def _cria_turmas_com_aluno(professor):
    """Turma do professor com 1 aluno; outra turma sem vínculo com o professor."""
    turma_do_professor = TurmaFactory(professores=[professor])
    aluno = AlunoFactory(turma=turma_do_professor)
    outra_turma = TurmaFactory()
    outro_aluno = AlunoFactory(turma=outra_turma)
    return aluno, outro_aluno


def test_relatorio_list_exige_autenticacao(api_client, db):
    response = api_client.get(LIST_URL)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_relatorio_detail_de_turma_alheia_retorna_404(auth_client, db, user):
    _, outro_aluno = _cria_turmas_com_aluno(user)
    relatorio = RelatorioFactory(aluno=outro_aluno)
    url = reverse("relatorio-detail", args=[relatorio.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    # LGPD: dados de aluno de outra turma nunca são expostos ao professor.
    assert response.json().get("dados") is None


def test_relatorio_sem_turma_nao_e_visto_por_professor(auth_client, db):
    aluno = AlunoFactory(turma=None)
    relatorio = RelatorioFactory(aluno=aluno)
    url = reverse("relatorio-detail", args=[relatorio.pk])
    response = auth_client.get(url)
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_relatorio_list_filtra_por_aluno(auth_client, db, user):
    aluno, outro_aluno = _cria_turmas_com_aluno(user)
    meu = RelatorioFactory(aluno=aluno, dados={"resumo": "bom"})
    RelatorioFactory(aluno=outro_aluno, dados={"resumo": "alheio"})
    response = auth_client.get(LIST_URL, {"aluno": aluno.pk})
    assert response.status_code == status.HTTP_200_OK
    ids = [item["id"] for item in response.data["results"]]
    assert ids == [meu.pk]


def test_relatorio_list_nao_retorna_turmas_alheias(auth_client, db, user):
    _, outro_aluno = _cria_turmas_com_aluno(user)
    alheio = RelatorioFactory(aluno=outro_aluno)
    response = auth_client.get(LIST_URL)
    ids = [item["id"] for item in response.data["results"]]
    assert alheio.pk not in ids


def test_relatorio_create_sem_campos_retorna_400(auth_client, db):
    response = auth_client.post(LIST_URL, {})
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_relatorio_create_com_aluno_inexistente_retorna_400(auth_client, db):
    formulario = {"aluno": 99999, "dados": {"resumo": "x"}}
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_relatorio_create_aluno_de_turma_alheia_retorna_400(auth_client, db, user):
    _, outro_aluno = _cria_turmas_com_aluno(user)
    formulario = {"aluno": outro_aluno.pk, "dados": {"resumo": "x"}}
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "aluno" in response.json()


def test_relatorio_create_valido(auth_client, db, user):
    aluno, _ = _cria_turmas_com_aluno(user)
    formulario = {"aluno": aluno.pk, "dados": {"resumo": "bom desempenho"}}
    response = auth_client.post(LIST_URL, formulario, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["aluno"] == aluno.pk
    assert response.data["dados"] == {"resumo": "bom desempenho"}

def test_relatorios_por_aluno_retorna_apenas_relatorios_do_aluno(
    auth_client, db, user
):
    aluno, outro_aluno = _cria_turmas_com_aluno(user)
    meu = RelatorioFactory(aluno=aluno, tipo="atividade")
    RelatorioFactory(aluno=outro_aluno, tipo="geral")

    url = reverse("aluno-relatorios", args=[aluno.pk])
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_200_OK

    resultados = (
        response.data["results"]
        if isinstance(response.data, dict)
        else response.data
    )
    ids = [item["id"] for item in resultados]

    assert ids == [meu.pk]
    assert resultados[0]["tipo"] == "atividade"
    assert resultados[0]["disclaimer"] == DISCLAIMER


def test_relatorios_por_aluno_de_outra_turma_retorna_404(
    auth_client, db, user
):
    _, outro_aluno = _cria_turmas_com_aluno(user)

    url = reverse("aluno-relatorios", args=[outro_aluno.pk])
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_relatorios_por_aluno_filtra_por_tipo(
    auth_client, db, user
):
    aluno, _ = _cria_turmas_com_aluno(user)
    atividade = RelatorioFactory(aluno=aluno, tipo="atividade")
    RelatorioFactory(aluno=aluno, tipo="geral")

    url = reverse("aluno-relatorios", args=[aluno.pk])
    response = auth_client.get(url, {"tipo": "atividade"})

    assert response.status_code == status.HTTP_200_OK

    resultados = (
        response.data["results"]
        if isinstance(response.data, dict)
        else response.data
    )
    assert [item["id"] for item in resultados] == [atividade.pk]


def test_relatorios_por_aluno_filtra_por_atividade(
    auth_client, db, user
):
    aluno, _ = _cria_turmas_com_aluno(user)
    atividade = AtividadeFactory(turma=aluno.turma, criada_por=user)
    relatorio_vinculado = RelatorioFactory(aluno=aluno, atividade=atividade)
    relatorio_sem_vinculo = RelatorioFactory(aluno=aluno)

    url = reverse("aluno-relatorios", args=[aluno.pk])
    response = auth_client.get(url, {"atividade": atividade.pk})

    assert response.status_code == status.HTTP_200_OK

    resultados = (
        response.data["results"]
        if isinstance(response.data, dict)
        else response.data
    )
    assert [item["id"] for item in resultados] == [
        relatorio_vinculado.pk
    ]
    assert relatorio_sem_vinculo.pk not in [
        item["id"] for item in resultados
    ]


def test_pdf_individual_retorna_application_pdf(
    auth_client, db, user
):
    aluno, _ = _cria_turmas_com_aluno(user)
    relatorio = RelatorioFactory(aluno=aluno)

    url = reverse("relatorio-pdf", args=[relatorio.pk])
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_pdf_consolidado_retorna_application_pdf(
    auth_client, db, user
):
    aluno, _ = _cria_turmas_com_aluno(user)
    RelatorioFactory(aluno=aluno, dados={"resumo": "Bom desempenho"})
    RelatorioFactory(aluno=aluno, dados={"resumo": "Boa participação"})

    url = reverse("aluno-relatorios-pdf", args=[aluno.pk])
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response["Content-Type"] == "application/pdf"
    assert response.content.startswith(b"%PDF-")


def test_pdf_consolidado_de_aluno_de_outra_turma_retorna_404(
    auth_client, db, user
):
    _, outro_aluno = _cria_turmas_com_aluno(user)

    url = reverse("aluno-relatorios-pdf", args=[outro_aluno.pk])
    response = auth_client.get(url)

    assert response.status_code == status.HTTP_404_NOT_FOUND
