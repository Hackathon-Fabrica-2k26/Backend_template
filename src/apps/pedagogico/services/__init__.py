"""Serviços do app pedagógico."""

from .anonimizar import anonimizar
from .extracao import MAX_TAMANHO_BYTES, ExtracaoError, extrair_texto, identificar_origem
from .habilidades import (
    CODIGOS_HABILIDADES,
    HABILIDADES,
    MIN_TRABALHOS_HABILIDADE,
    NOMES_HABILIDADES,
    calcular_habilidades_aluno,
    calcular_habilidades_turma,
    filtrar_codigos,
)
from .llm import (
    DISCLAIMER,
    MODELO_PADRAO,
    SYSTEM_PROMPT,
    LLMError,
    extrair_atividade_multimodal,
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
from .variacoes import (
    MAX_GRUPOS_ADAPTADOS,
    PROMPT_VARIACAO_ATIVIDADE,
    agrupar_perfis_apoio,
    gerar_variacoes_atividade,
)

__all__ = [
    "CODIGOS_HABILIDADES",
    "DISCLAIMER",
    "ExtracaoError",
    "FORMATOS_ACEITOS",
    "HABILIDADES",
    "LLMError",
    "MAX_GRUPOS_ADAPTADOS",
    "MAX_TAMANHO_BYTES",
    "MIN_TRABALHOS_HABILIDADE",
    "MODELO_PADRAO",
    "NOMES_HABILIDADES",
    "PROMPT_VARIACAO_ATIVIDADE",
    "SYSTEM_PROMPT",
    "TAMANHO_MAXIMO_BYTES",
    "agrupar_perfis_apoio",
    "analisar_trabalho_com_gemini",
    "anonimizar",
    "calcular_habilidades_aluno",
    "calcular_habilidades_turma",
    "casar_nome_aluno",
    "confirmar_trabalho",
    "extrair_texto",
    "extrair_texto_docx",
    "filtrar_codigos",
    "gerar_relatorio",
    "gerar_variacoes_atividade",
    "identificar_origem",
    "processar_envio_trabalhos",
    "sugerir_atividade",
    "validar_arquivos_envio",
    "extrair_atividade_multimodal",
]
