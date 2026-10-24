"""Testes do endpoint POST /api/relatorios/gerar/ (view + LLM mockada)."""

from apps.pedagogico.models import Relatorio
from apps.pedagogico.services import DISCLAIMER

from .factories import AlunoFactory, EscolaFactory, ResponsavelFactory, TurmaFactory

GERAR_URL = "/api/relatorios/gerar/"

RESPOSTA_FAKE = (
    "```json\n"
    '{"radar": [70, 80], "pontos_fortes": ["criatividade nas aulas"], '
    '"necessidades": ["atenção nos estudos"], '
    '"atividades": [{"titulo": "Jogo das sombras", "descricao": "Explorar luz e sombra"}], '
    '"dica_de_autonomia": "Manter rotina de estudos", "observacoes": null}'
    "\n```"
)


def _monta_alunos(user):
    """Turma do professor com aluno e responsável; outro aluno em turma alheia."""
    user.escola = EscolaFactory()
    user.save()
    turma = TurmaFactory(escola=user.escola, professores=[user])
    responsavel = ResponsavelFactory(nome="Maria da Silva")
    aluno = AlunoFactory(nome="João da Silva", turma=turma, responsavel=responsavel)
    outro_aluno = AlunoFactory(turma=TurmaFactory())
    return aluno, outro_aluno


def _formulario(aluno):
    return {
        "aluno": aluno.pk,
        "pontos_fortes": ["João da Silva é criativo"],
        "desafios": ["Documentos com CPF 123.456.789-09"],
        "contexto_turma": "Nasceu 10/03/2017 e tem muita energia na sala.",
    }


def test_gerar_relatorio_exige_autenticacao(api_client, db):
    response = api_client.post(GERAR_URL, {}, format="json")
    assert response.status_code == 401


def test_gerar_relatorio_aluno_de_turma_alheia_retorna_404(auth_client, db, user):
    _, outro_aluno = _monta_alunos(user)
    response = auth_client.post(GERAR_URL, _formulario(outro_aluno), format="json")
    assert response.status_code == 404


def test_gerar_relatorio_aluno_sem_turma_retorna_404(auth_client, db, user):
    _monta_alunos(user)
    sem_turma = AlunoFactory(turma=None)
    response = auth_client.post(GERAR_URL, _formulario(sem_turma), format="json")
    assert response.status_code == 404


def test_gerar_relatorio_sem_campos_retorna_400(auth_client, db):
    response = auth_client.post(GERAR_URL, {}, format="json")
    assert response.status_code == 400
    assert "aluno" in response.json()


def test_gerar_relatorio_sucesso_salva_relatorio_e_atividade(auth_client, db, user, monkeypatch):
    """Fluxo completo: salva Relatorio + Atividade e devolve payload anonimizado."""
    capturado = {}

    def fake(conteudo, api_key, modelo):
        capturado.update({"conteudo": conteudo, "api_key": api_key, "modelo": modelo})
        return RESPOSTA_FAKE

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake)
    aluno, _ = _monta_alunos(user)
    response = auth_client.post(GERAR_URL, _formulario(aluno), format="json")

    assert response.status_code == 201
    corpo = response.json()
    relatorio = Relatorio.objects.get(pk=corpo["relatorio"]["id"])
    assert corpo["relatorio"]["aluno"] == aluno.pk
    assert corpo["relatorio"]["dados"]["radar"] == [70, 80]
    assert relatorio.disclaimer == DISCLAIMER

    payload = corpo["payload_enviado"]
    assert "aluno" not in payload
    assert payload["codinome_aluno"].startswith("Aluno ")
    # Credenciais da escola configurada foram usadas na chamada.
    assert capturado["api_key"] == user.escola.config.api_key
    assert capturado["modelo"] == user.escola.config.modelo


def test_gerar_relatorio_payload_nao_vaza_pii(auth_client, db, user, monkeypatch):
    """Nome real, CPF, responsável e data nunca vão no conteúdo enviado à LLM."""
    capturado = {}

    def fake(conteudo, api_key, modelo):
        capturado["conteudo"] = conteudo
        return RESPOSTA_FAKE

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake)
    aluno, _ = _monta_alunos(user)
    response = auth_client.post(GERAR_URL, _formulario(aluno), format="json")

    assert response.status_code == 201
    texto = capturado["conteudo"].lower()
    assert "joão" not in texto
    assert "maria" not in texto
    assert "123.456.789-09" not in texto
    assert "10/03/2017" not in texto
    # A troca pelo codinome foi real: o nome não fica mascarado em partes.
    payload = response.json()["payload_enviado"]
    assert payload["pontos_fortes"] == [f"{payload['codinome_aluno']} é criativo"]


def test_gerar_relatorio_com_llm_fora_do_ar_retorna_502(auth_client, db, user, monkeypatch):
    def fake(conteudo, api_key, modelo):
        raise RuntimeError("API morreu")

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake)
    aluno, _ = _monta_alunos(user)
    response = auth_client.post(GERAR_URL, _formulario(aluno), format="json")

    assert response.status_code == 502
    assert "Não foi possível gerar o relatório" in response.json()["erro"]


def test_gerar_relatorio_sem_credencial_da_escola_retorna_502(auth_client, db, user):
    """Escola sem api_key recebe 502 com mensagem amigável."""
    user.escola = None
    user.save()
    turma = TurmaFactory(professores=[user], escola__config__api_key="")
    aluno = AlunoFactory(turma=turma)

    response = auth_client.post(GERAR_URL, _formulario(aluno), format="json")

    assert response.status_code == 502
    assert "credencial" in response.json()["erro"]
