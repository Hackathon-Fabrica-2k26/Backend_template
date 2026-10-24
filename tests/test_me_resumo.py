import pytest

from apps.escolas.models.turma import ano_letivo_atual
from apps.pedagogico.models import Trabalho

from .factories import (
    AtividadeFactory,
    EnvioTrabalhosFactory,
    TrabalhoFactory,
    TurmaFactory,
    UserFactory,
)

URL = "/api/auth/me/resumo/"


@pytest.mark.django_db
def test_resumo_exige_autenticacao(api_client):
    assert api_client.get(URL).status_code == 401


@pytest.mark.django_db
def test_resumo_sem_dados(auth_client):
    resp = auth_client.get(URL)
    assert resp.status_code == 200
    assert resp.json() == {"turmas": 0, "atividades": 0, "trabalhos_analisados": 0}


@pytest.mark.django_db
def test_resumo_conta_apenas_dados_do_professor(auth_client, user):
    outro = UserFactory()
    turma = TurmaFactory(professores=[user])
    TurmaFactory(professores=[user, outro])
    TurmaFactory(professores=[user], ano_letivo=ano_letivo_atual() - 1)
    turma_outro = TurmaFactory(professores=[outro])

    atividade = AtividadeFactory(turma=turma, criada_por=user)
    AtividadeFactory(turma=turma, criada_por=user)
    atividade_outro = AtividadeFactory(turma=turma_outro, criada_por=outro)

    envio = EnvioTrabalhosFactory(atividade=atividade, enviado_por=user)
    TrabalhoFactory(envio=envio)
    TrabalhoFactory(envio=envio)
    TrabalhoFactory(envio=envio, status=Trabalho.StatusChoices.ANALISANDO)
    TrabalhoFactory(envio=EnvioTrabalhosFactory(atividade=atividade_outro, enviado_por=outro))

    resp = auth_client.get(URL)
    assert resp.status_code == 200
    assert resp.json() == {"turmas": 2, "atividades": 2, "trabalhos_analisados": 2}
