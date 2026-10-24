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
from .variacoes import (
    MAX_GRUPOS_ADAPTADOS,
    PROMPT_VARIACAO_ATIVIDADE,
    agrupar_perfis_apoio,
    gerar_variacoes_atividade,
)

__all__ = [
    "DISCLAIMER",
    "ExtracaoError",
    "LLMError",
    "MAX_GRUPOS_ADAPTADOS",
    "MAX_TAMANHO_BYTES",
    "MODELO_PADRAO",
    "PROMPT_VARIACAO_ATIVIDADE",
    "SYSTEM_PROMPT",
    "agrupar_perfis_apoio",
    "anonimizar",
    "extrair_texto",
    "gerar_relatorio",
    "gerar_variacoes_atividade",
    "identificar_origem",
    "sugerir_atividade",
]
