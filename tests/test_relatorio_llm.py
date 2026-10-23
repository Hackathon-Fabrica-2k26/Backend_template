"""Testes da geração de relatório com LLM: anonimização + Gemini mockado."""

import json

import pytest

from apps.pedagogico.services.anonimizar import anonimizar
from apps.pedagogico.services.llm import DISCLAIMER, LLMError, gerar_relatorio

PAYLOAD_COM_PII = {"nome": "João da Silva", "cpf": "123.456.789-09"}

PAYLOAD_OK = {"codinome_aluno": "Aluno Alfa", "pontos_fortes": ["participa"]}

RESPOSTA_FAKE = (
    "```json\n"
    '{"radar": [10], "pontos_fortes": ["colabora com os colegas"], '
    '"necessidades": [], "atividades": [{"titulo": "Contagem na feira", "descricao": "..."}], '
    '"dica_de_autonomia": null, "observacoes": "ok"}'
    "\n```"
)


def test_payload_anonimizado_nao_tem_pii():
    """O payload enviado à LLM não contém nome real nem CPF."""
    dados = {
        "pontos_fortes": [PAYLOAD_COM_PII["nome"] + " participa bem das aulas"],
        "desafios": ["Documento nele é " + PAYLOAD_COM_PII["cpf"]],
        "contexto_turma": "Responsável: Maria da Silva",
        "responsavel": "Maria da Silva",
        "cpf": PAYLOAD_COM_PII["cpf"],
        "aluno": 7,
    }
    payload = anonimizar(dados, PAYLOAD_COM_PII["nome"])

    texto = json.dumps(payload).lower()
    assert PAYLOAD_COM_PII["nome"].lower() not in texto
    assert "maria" not in texto
    assert PAYLOAD_COM_PII["cpf"] not in texto
    assert "123.456.789-09" not in texto
    for chave in ("cpf", "responsavel", "aluno"):
        assert chave not in payload
    assert payload["codinome_aluno"].startswith("Aluno ")


def test_gerar_relatorio_com_llm_mockada(monkeypatch):
    """A resposta da LLM é extraída como JSON e recebe o disclaimer."""
    capturado = {}

    def fake(conteudo, api_key, modelo):
        capturado.update({"conteudo": conteudo, "api_key": api_key, "modelo": modelo})
        return RESPOSTA_FAKE

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake)
    resposta = gerar_relatorio(PAYLOAD_OK, "chave-secreta-da-escola", modelo="gemini-2.5-flash")

    assert resposta["radar"] == [10]
    assert resposta["atividades"][0]["titulo"] == "Contagem na feira"
    assert resposta["disclaimer"] == DISCLAIMER
    assert capturado["api_key"] == "chave-secreta-da-escola"
    assert capturado["modelo"] == "gemini-2.5-flash"
    assert "Aluno Alfa" in capturado["conteudo"]
    assert json.dumps(PAYLOAD_COM_PII) not in capturado["conteudo"]


def test_erro_da_llm_vira_excecao_amigavel(monkeypatch):
    """Qualquer falha na LLM vira LLMError com mensagem amigável."""

    def fake(conteudo, api_key, modelo):
        raise RuntimeError("API morreu")

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake)
    with pytest.raises(LLMError) as erro:
        gerar_relatorio(PAYLOAD_OK, "chave-secreta-da-escola")
    assert "Não foi possível gerar o relatório" in str(erro.value)


def test_resposta_sem_json(monkeypatch):
    """Resposta sem JSON válido também é falha esperada."""
    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", lambda *a: "texto solto")
    with pytest.raises(LLMError):
        gerar_relatorio(PAYLOAD_OK, "chave-secreta-da-escola")


def test_api_key_ausente():
    """Sem credencial configurada, o serviço falha cedo e com mensagem clara."""
    with pytest.raises(LLMError) as erro:
        gerar_relatorio(PAYLOAD_OK, "")
    assert "credencial" in str(erro.value)


def test_llm_devolvendo_lista_vira_erro(monkeypatch):
    """JSON válido que não é um objeto (ex.: lista) também é LLMError, não TypeError."""
    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", lambda *a: "[1, 2, 3]")
    with pytest.raises(LLMError):
        gerar_relatorio(PAYLOAD_OK, "chave-secreta-da-escola")


def test_chaves_sensiveis_sem_diferenciar_maiusculas():
    """Variações de maiúsculas nas chaves ("Nome", "CPF", "Cidade") são removidas."""
    dados = {
        "Nome": "João",
        "CPF": "123.456.789-09",
        "Cidade": "Campinas",
        "Data de Nascimento": "10/03/2017",
        "titulo": "atividade de frações",
    }
    payload = anonimizar(dados)
    texto = json.dumps(payload).lower()
    assert "nome" not in payload
    assert "cpf" not in payload
    assert "cidade" not in payload
    assert "data de nascimento" not in texto
    assert payload == {"titulo": "atividade de frações"}


def test_primeiro_nome_isolado_tambem_vira_codinome():
    """Só o primeiro nome aparece em algum trecho: também é trocado pelo codinome."""
    dados = {"desafios": ["João precisa de reforço; João ainda erra as frações"]}
    payload = anonimizar(dados, nome_aluno="João da Silva")
    texto = json.dumps(payload, ensure_ascii=False)
    assert "João" not in texto
    texto_sem_codinome = texto.replace("codinome_aluno", "")
    assert payload["codinome_aluno"] in texto_sem_codinome


def test_e2e_anonimizar_gerar_relatorio_nao_vaza_pii(monkeypatch):
    """anonimizar() -> gerar_relatorio(): nome, CPF, responsável e data nunca
    chegam ao conteudo enviado à LLM."""
    capturado = {}

    def fake(conteudo, api_key, modelo):
        capturado.update({"conteudo": conteudo, "api_key": api_key})
        return RESPOSTA_FAKE

    monkeypatch.setattr("apps.pedagogico.services.llm._pedir_ao_gemini", fake)

    dados = {
        "aluno": 3,
        "pontos_fortes": ["João da Silva é criativo e ajuda os colegas", "JOÃO é atento"],
        "desafios": ["Apresenta nos documentos o CPF 123.456.789-09"],
        "contexto_turma": "Nasceu 10/03/2017. Responsável legal: Maria da Silva visitou reunião.",
    }
    payload = anonimizar(dados, nome_aluno="João da Silva", nome_responsavel="Maria da Silva")
    resposta = gerar_relatorio(payload, "chave-secreta-da-escola")

    assert resposta["disclaimer"] == DISCLAIMER
    texto = capturado["conteudo"].lower()
    assert "joão" not in texto
    assert "maria" not in texto
    assert "123.456.789-09" not in texto
    assert "10/03/2017" not in texto
    assert payload["codinome_aluno"].startswith("Aluno ")
