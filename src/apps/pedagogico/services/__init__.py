"""Serviços do app pedagógico."""

from .anonimizar import anonimizar
from .llm import DISCLAIMER, MODELO_PADRAO, SYSTEM_PROMPT, LLMError, gerar_relatorio
from .trabalhos import (
    TAMANHO_MAXIMO_BYTES,
    analisar_trabalho_com_gemini,
    casar_nome_aluno,
    confirmar_trabalho,
    extrair_texto_docx,
    gravar_relatorio_atividade,
    normalizar_texto,
    obter_alunos_da_atividade,
    processar_envio_trabalhos,
    professor_tem_acesso,
    validar_arquivo,
)

__all__ = [
    "DISCLAIMER",
    "LLMError",
    "MODELO_PADRAO",
    "SYSTEM_PROMPT",
    "TAMANHO_MAXIMO_BYTES",
    "analisar_trabalho_com_gemini",
    "anonimizar",
    "casar_nome_aluno",
    "confirmar_trabalho",
    "extrair_texto_docx",
    "gerar_relatorio",
    "gravar_relatorio_atividade",
    "normalizar_texto",
    "obter_alunos_da_atividade",
    "processar_envio_trabalhos",
    "professor_tem_acesso",
    "validar_arquivo",
]
