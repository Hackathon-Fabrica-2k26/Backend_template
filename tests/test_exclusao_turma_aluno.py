import pytest
from rest_framework import status

from apps.alunos.models import Aluno
from apps.escolas.models import Turma
from apps.pedagogico.models import Atividade

from .factories import AlunoFactory, AtividadeFactory, TurmaFactory, UserFactory

pytestmark = pytest.mark.django_db


def test_excluir_turma_leva_alunos_e_atividades_junto(auth_client, user):
    turma = TurmaFactory(professores=[user])
    aluno = AlunoFactory(turma=turma)
    atividade = AtividadeFactory(turma=turma, criada_por=user)

    resp = auth_client.delete(f"/api/turmas/{turma.id}/")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Turma.objects.filter(pk=turma.pk).exists()
    assert not Aluno.objects.filter(pk=aluno.pk).exists()
    assert not Atividade.objects.filter(pk=atividade.pk).exists()


def test_excluir_turma_de_outro_professor_da_404(auth_client):
    turma = TurmaFactory(professores=[UserFactory()])
    assert auth_client.delete(f"/api/turmas/{turma.id}/").status_code == 404
    assert Turma.objects.filter(pk=turma.pk).exists()


def test_excluir_aluno_da_turma(auth_client, user):
    turma = TurmaFactory(professores=[user])
    aluno, outro = AlunoFactory(turma=turma), AlunoFactory(turma=turma)

    resp = auth_client.delete(f"/api/alunos/{aluno.id}/")

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert list(Aluno.objects.filter(turma=turma)) == [outro]


def test_excluir_aluno_de_outro_professor_da_404(auth_client):
    aluno = AlunoFactory(turma=TurmaFactory(professores=[UserFactory()]))
    assert auth_client.delete(f"/api/alunos/{aluno.id}/").status_code == 404
