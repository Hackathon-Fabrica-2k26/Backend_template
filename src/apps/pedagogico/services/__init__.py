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
from .trabalhos import (
    FORMATOS_ACEITOS,
    TAMANHO_MAXIMO_BYTES,
    analisar_trabalho_com_gemini,
    casar_nome_aluno,
    confirmar_trabalho,
    extrair_texto_docx,
    processar_envio_trabalhos,
    validar_arquivos_envio,
)

__all__ = [
    "DISCLAIMER",
    "ExtracaoError",
    "FORMATOS_ACEITOS",
    "LLMError",
    "MAX_TAMANHO_BYTES",
    "MODELO_PADRAO",
    "SYSTEM_PROMPT",
    "TAMANHO_MAXIMO_BYTES",
    "analisar_trabalho_com_gemini",
    "anonimizar",
    "casar_nome_aluno",
    "confirmar_trabalho",
    "extrair_texto",
    "extrair_texto_docx",
    "gerar_relatorio",
    "identificar_origem",
    "processar_envio_trabalhos",
    "sugerir_atividade",
    "validar_arquivos_envio",
]
