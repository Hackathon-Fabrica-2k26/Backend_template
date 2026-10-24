from datetime import timedelta

import pytest
from django.core.signing import TimestampSigner
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.alunos.models import AlunoResponsavel, CodigoAcessoAluno, Consentimento, Responsavel
from apps.alunos.services.codigo_acesso import SALT_TOKEN, hash_codigo
from apps.pedagogico.models import PerfilApoio

from .factories import AlunoFactory, PerfilApoioFactory, TurmaFactory, UserFactory


@pytest.fixture
def aluno(user):
    return AlunoFactory(turma=TurmaFactory(professores=[user]), consentimento=False)


def gerar(auth_client, aluno):
    resposta = auth_client.post(reverse("aluno-codigo-acesso", args=[aluno.pk]))
    assert resposta.status_code == status.HTTP_201_CREATED
    return resposta.json()["codigo"]


def acessar(codigo, **extra):
    corpo = {"codigo": codigo, "nome": "Maria", **extra}
    return APIClient().post(reverse("responsavel-acesso"), corpo, format="json")


def cliente_responsavel(aluno, **extra):
    codigo_resp = None
    professor = aluno.turma.professores.first()
    c = APIClient()
    c.force_authenticate(user=professor)
    codigo_resp = c.post(reverse("aluno-codigo-acesso", args=[aluno.pk])).json()["codigo"]
    token = acessar(codigo_resp, **extra).json()["token"]
    resp = APIClient()
    resp.credentials(HTTP_AUTHORIZATION=f"Responsavel {token}")
    return resp


# --- geração / revogação pela professora ---------------------------------------------------


def test_gerar_codigo_guarda_so_hash(auth_client, aluno):
    codigo = gerar(auth_client, aluno)
    assert len(codigo) == 8
    registro = CodigoAcessoAluno.objects.get(aluno=aluno)
    assert registro.codigo_hash == hash_codigo(codigo)
    assert codigo not in registro.codigo_hash
    assert registro.expira_em - registro.gerado_em == timedelta(days=7)
    assert registro.gerado_por_id is not None


def test_gerar_novo_codigo_revoga_anterior(auth_client, aluno):
    antigo = gerar(auth_client, aluno)
    novo = gerar(auth_client, aluno)
    assert antigo != novo
    assert CodigoAcessoAluno.objects.filter(aluno=aluno, revogado_em__isnull=True).count() == 1
    assert acessar(antigo).status_code == status.HTTP_400_BAD_REQUEST
    assert acessar(novo).status_code == status.HTTP_200_OK


def test_revogar_codigo(auth_client, aluno):
    codigo = gerar(auth_client, aluno)
    resposta = auth_client.post(reverse("aluno-codigo-acesso-revogar", args=[aluno.pk]))
    assert resposta.status_code == status.HTTP_200_OK
    assert resposta.json() == {"revogados": 1}
    assert acessar(codigo).status_code == status.HTTP_400_BAD_REQUEST


def test_professor_de_outra_turma_nao_gera_nem_revoga(auth_client, db):
    alheio = AlunoFactory()
    assert (
        auth_client.post(reverse("aluno-codigo-acesso", args=[alheio.pk])).status_code
        == status.HTTP_404_NOT_FOUND
    )
    assert (
        auth_client.post(reverse("aluno-codigo-acesso-revogar", args=[alheio.pk])).status_code
        == status.HTTP_404_NOT_FOUND
    )


def test_geracao_exige_autenticacao(api_client, aluno):
    resposta = api_client.post(reverse("aluno-codigo-acesso", args=[aluno.pk]))
    assert resposta.status_code == status.HTTP_401_UNAUTHORIZED


# --- acesso do responsável por código -------------------------------------------------------


def test_acesso_cria_responsavel_vincula_e_marca_uso(auth_client, aluno):
    codigo = gerar(auth_client, aluno)
    resposta = acessar(codigo.lower(), email="maria@example.com", parentesco="mãe")
    assert resposta.status_code == status.HTTP_200_OK
    assert resposta.json()["token"]
    responsavel = Responsavel.objects.get(email="maria@example.com")
    vinculo = AlunoResponsavel.objects.get(aluno=aluno, responsavel=responsavel)
    assert vinculo.parentesco == "mãe"
    assert CodigoAcessoAluno.objects.get(aluno=aluno).usado_em is not None
    assert list(aluno.responsaveis.all()) == [responsavel]


def test_codigo_so_pode_ser_usado_uma_vez(auth_client, aluno):
    codigo = gerar(auth_client, aluno)
    assert acessar(codigo).status_code == status.HTTP_200_OK
    assert acessar(codigo).status_code == status.HTTP_400_BAD_REQUEST


def test_codigo_expirado_e_invalido(auth_client, aluno):
    codigo = gerar(auth_client, aluno)
    CodigoAcessoAluno.objects.update(expira_em=timezone.now() - timedelta(seconds=1))
    assert acessar(codigo).status_code == status.HTTP_400_BAD_REQUEST
    assert Responsavel.objects.count() == 0


def test_codigo_inexistente_e_invalido(db):
    assert acessar("ZZZZZZZZ").status_code == status.HTTP_400_BAD_REQUEST


def test_acesso_reaproveita_responsavel_por_email(auth_client, user, aluno):
    irmao = AlunoFactory(turma=aluno.turma, consentimento=False)
    acessar(gerar(auth_client, aluno), email="maria@example.com")
    acessar(gerar(auth_client, irmao), email="MARIA@example.com")
    assert Responsavel.objects.count() == 1
    assert AlunoResponsavel.objects.count() == 2


def test_acesso_sem_nome_retorna_400(auth_client, aluno):
    codigo = gerar(auth_client, aluno)
    resposta = APIClient().post(reverse("responsavel-acesso"), {"codigo": codigo}, format="json")
    assert resposta.status_code == status.HTTP_400_BAD_REQUEST


def test_acesso_tem_throttle(db):
    for _ in range(10):
        assert acessar("ZZZZZZZZ").status_code == status.HTTP_400_BAD_REQUEST
    assert acessar("ZZZZZZZZ").status_code == status.HTTP_429_TOO_MANY_REQUESTS


# --- autenticação do responsável ------------------------------------------------------------


def test_aluno_do_responsavel_expoe_so_nome_turma_e_consentimento(auth_client, aluno):
    c = cliente_responsavel(aluno)
    resposta = c.get(reverse("responsavel-aluno"))
    assert resposta.status_code == status.HTTP_200_OK
    assert resposta.json() == {
        "nome": aluno.nome,
        "turma": aluno.turma.nome,
        "consentimento_ativo": False,
    }


def test_sem_token_ou_token_invalido_401(auth_client, aluno):
    assert APIClient().get(reverse("responsavel-aluno")).status_code == status.HTTP_401_UNAUTHORIZED
    ruim = APIClient()
    ruim.credentials(HTTP_AUTHORIZATION="Responsavel abc")
    assert ruim.get(reverse("responsavel-aluno")).status_code == status.HTTP_401_UNAUTHORIZED


def test_token_expirado_apos_24h(auth_client, aluno, monkeypatch):
    c = cliente_responsavel(aluno)
    import time

    real = time.time
    monkeypatch.setattr(time, "time", lambda: real() + 24 * 3600 + 5)
    assert c.get(reverse("responsavel-aluno")).status_code == status.HTTP_401_UNAUTHORIZED


def test_token_adulterado_ou_de_outro_salt_e_rejeitado(auth_client, aluno):
    responsavel = Responsavel.objects.create(nome="X")
    AlunoResponsavel.objects.create(aluno=aluno, responsavel=responsavel)
    falso = TimestampSigner(salt="outro").sign(f"{responsavel.pk}:{aluno.pk}")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Responsavel {falso}")
    assert c.get(reverse("responsavel-aluno")).status_code == status.HTTP_401_UNAUTHORIZED
    valido = TimestampSigner(salt=SALT_TOKEN).sign(f"{responsavel.pk}:{aluno.pk}")
    c.credentials(HTTP_AUTHORIZATION=f"Responsavel {valido}")
    assert c.get(reverse("responsavel-aluno")).status_code == status.HTTP_200_OK


def test_token_do_responsavel_nao_vale_em_rotas_da_professora(auth_client, aluno):
    c = cliente_responsavel(aluno)
    assert c.get(reverse("aluno-list")).status_code == status.HTTP_401_UNAUTHORIZED


def test_jwt_da_professora_nao_vale_em_rotas_do_responsavel(auth_client):
    assert auth_client.get(reverse("responsavel-aluno")).status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )


def test_vinculo_removido_invalida_token(auth_client, aluno):
    c = cliente_responsavel(aluno)
    AlunoResponsavel.objects.all().delete()
    assert c.get(reverse("responsavel-aluno")).status_code == status.HTTP_401_UNAUTHORIZED


# --- consentimento --------------------------------------------------------------------------


def test_responsavel_cria_e_revoga_consentimento(auth_client, aluno):
    PerfilApoioFactory(aluno=aluno)
    c = cliente_responsavel(aluno, email="maria@example.com")

    criado = c.post(reverse("responsavel-consentimento"))
    assert criado.status_code == status.HTTP_201_CREATED
    consentimento = Consentimento.objects.get(aluno=aluno)
    assert consentimento.responsavel.email == "maria@example.com"
    assert c.get(reverse("responsavel-aluno")).json()["consentimento_ativo"] is True
    assert c.post(reverse("responsavel-consentimento")).status_code == status.HTTP_400_BAD_REQUEST

    revogado = c.post(reverse("responsavel-consentimento-revogar"))
    assert revogado.status_code == status.HTTP_200_OK
    consentimento.refresh_from_db()
    assert consentimento.revogado_em is not None
    assert not PerfilApoio.all_objects.filter(aluno=aluno).exists()
    assert c.get(reverse("responsavel-aluno")).json()["consentimento_ativo"] is False


def test_revogar_sem_consentimento_ativo_retorna_400(auth_client, aluno):
    c = cliente_responsavel(aluno)
    resposta = c.post(reverse("responsavel-consentimento-revogar"))
    assert resposta.status_code == status.HTTP_400_BAD_REQUEST


# --- isolamento -----------------------------------------------------------------------------


def test_isolamento_entre_responsaveis(db):
    prof_a, prof_b = UserFactory(), UserFactory()
    aluno_a = AlunoFactory(turma=TurmaFactory(professores=[prof_a]), consentimento=False)
    aluno_b = AlunoFactory(turma=TurmaFactory(professores=[prof_b]), consentimento=False)
    resp_a = cliente_responsavel(aluno_a)
    resp_b = cliente_responsavel(aluno_b)

    assert resp_a.get(reverse("responsavel-aluno")).json()["nome"] == aluno_a.nome
    assert resp_b.get(reverse("responsavel-aluno")).json()["nome"] == aluno_b.nome

    assert resp_a.post(reverse("responsavel-consentimento")).status_code == 201
    assert Consentimento.objects.filter(aluno=aluno_a).count() == 1
    assert not Consentimento.objects.filter(aluno=aluno_b).exists()
    assert resp_b.get(reverse("responsavel-aluno")).json()["consentimento_ativo"] is False

    # B não consegue revogar o consentimento do filho de A.
    assert (
        resp_b.post(reverse("responsavel-consentimento-revogar")).status_code
        == status.HTTP_400_BAD_REQUEST
    )
    assert Consentimento.objects.get(aluno=aluno_a).revogado_em is None


# --- schema / api_root ----------------------------------------------------------------------


def test_api_root_lista_rotas_novas(auth_client):
    corpo = auth_client.get(reverse("api-root")).json()
    for chave in (
        "aluno-codigo-acesso",
        "aluno-codigo-acesso-revogar",
        "responsavel-acesso",
        "responsavel-aluno",
        "responsavel-consentimento",
        "responsavel-consentimento-revogar",
    ):
        assert chave in corpo
