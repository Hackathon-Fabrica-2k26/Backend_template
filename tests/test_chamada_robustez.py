from apps.escolas.services.chamada import _limpar_nomes
from apps.pedagogico.services.llm import MODELO_PADRAO, normalizar_modelo


def test_formato_com_duvida_vira_confianca():
    nomes = _limpar_nomes(
        [{"nome": "Ana Souza", "duvida": False}, {"nome": "B. Lima", "duvida": True}]
    )
    assert nomes == [
        {"nome": "Ana Souza", "confianca": 1.0},
        {"nome": "B. Lima", "confianca": 0.5},
    ]


def test_normalizar_modelo():
    assert normalizar_modelo("  models/gemini-3.8-flash ") == "gemini-3.8-flash"
    assert normalizar_modelo("") == MODELO_PADRAO
    assert normalizar_modelo(None) == MODELO_PADRAO
