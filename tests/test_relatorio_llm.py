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
