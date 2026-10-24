"""Serviços do app pedagógico."""

from .anonimizar import anonimizar
from .extracao import MAX_TAMANHO_BYTES, ExtracaoError, extrair_texto, identificar_origem
from .llm import (
    DISCLAIMER,
    MODELO_PADRAO,
    SYSTEM_PROMPT,
    LLMError,
    gerar_relatorio,
    sugerir_atividade,
)

__all__ = [
    "DISCLAIMER",
    "ExtracaoError",
    "LLMError",
    "MAX_TAMANHO_BYTES",
    "MODELO_PADRAO",
    "SYSTEM_PROMPT",
    "anonimizar",
    "extrair_texto",
    "gerar_relatorio",
    "identificar_origem",
    "sugerir_atividade",
]
