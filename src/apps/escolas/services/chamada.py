"""Reconhecimento de nomes de alunos em foto ou PDF de lista de chamada via Gemini (OCR).

O arquivo é processado exclusivamente em memória (bytes) e nunca é gravado em
disco, banco de dados ou logs (LGPD).
"""

import logging
import re

from apps.pedagogico.services.llm import (
    MAX_RESPOSTA_TOKENS,
    LLMError,
    _extrair_json,
    normalizar_modelo,
)

logger = logging.getLogger(__name__)

MENSAGEM_ERRO_PADRAO = (
    "Não foi possível reconhecer os nomes na imagem agora. Tente novamente em instantes."
)

SYSTEM_PROMPT_CHAMADA = (
    "Você é um assistente de OCR escolar. Analise a imagem ou documento PDF de "
    "uma lista de chamada e extraia APENAS a coluna de nomes completos dos estudantes.\n"
    "Regras obrigatórias:\n"
    "- Foque exclusivamente na coluna de nomes dos alunos.\n"
    "- Ignore completamente datas de nascimento, observações (médicas ou pedagógicas), "
    "números de chamada, códigos de matrícula, cabeçalhos, assinaturas, notas, "
    "marcações de presença/falta e qualquer outra coluna ou informação.\n"
    "- Mantenha exatamente a ordem em que os nomes aparecem na lista.\n"
    "- Não inclua nomes duplicados.\n"
    "- Não invente nomes que não estejam no documento.\n"
    "- Para cada nome, informe o índice de confiança de legibilidade (`confianca`) "
    "entre 0.0 (muito ilegível/duvidoso) e 1.0 (totalmente nítido).\n"
    "- Responda APENAS com um JSON válido no formato:\n"
    '  {"nomes": [{"nome": "Nome Completo 1", "confianca": 0.95}, ...]}'
)

PROMPT_USUARIO_CHAMADA = (
    "Extraia somente a coluna de nomes completos dos alunos desta lista de chamada "
    "(ignorando datas de nascimento, observações e demais colunas) e devolva "
    "exclusivamente um JSON no formato "
    '{"nomes": [{"nome": "...", "confianca": 0.95}]}.'
)

_PREFIXO_NUMERO_RE = re.compile(r"^\s*\d+\s*[\.\)\-–—:ºª]*\s*")
_DATA_RE = re.compile(r"\b(?:\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2})\b")


def reconhecer_nomes(
    imagem_bytes: bytes,
    mime: str,
    config,
) -> list[dict[str, str | float]]:
    """Envia o arquivo (imagem ou PDF) da lista de chamada ao Gemini e devolve
    a lista de nomes com confiança de legibilidade.

    Recebe os bytes do arquivo em memória, o MIME type validado e a ``Config``
    da escola do professor. Levanta ``LLMError`` se não houver credencial
    configurada ou se a chamada/resposta da LLM falhar.
    """
    api_key = getattr(config, "api_key", "") if config is not None else ""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")
    modelo = normalizar_modelo(getattr(config, "modelo", "") if config is not None else "")

    try:
        resposta = _pedir_ocr_ao_gemini(imagem_bytes, mime, api_key, modelo)
    except LLMError:
        raise
    except Exception as erro:
        logger.warning(
            "Chamada: erro inesperado ao chamar o Gemini (modelo=%s): %s: %s",
            modelo,
            type(erro).__name__,
            erro,
        )
        raise LLMError(MENSAGEM_ERRO_PADRAO) from erro
    try:
        dados = _extrair_json(resposta)
    except Exception as erro:
        # Não registra o conteúdo (pode ter nomes de alunos), só o tamanho.
        logger.warning(
            "Chamada: resposta do Gemini não é JSON válido (modelo=%s, %d caracteres)",
            modelo,
            len(resposta),
        )
        raise LLMError(MENSAGEM_ERRO_PADRAO) from erro

    if not isinstance(dados, dict) or not isinstance(dados.get("nomes"), list):
        logger.warning("Chamada: JSON do Gemini sem a lista 'nomes' (modelo=%s)", modelo)
        raise LLMError(MENSAGEM_ERRO_PADRAO)

    return _limpar_nomes(dados["nomes"])


def _pedir_ocr_ao_gemini(imagem_bytes: bytes, mime: str, api_key: str, modelo: str) -> str:
    """Envia a imagem ou PDF em memória ao Gemini e devolve o texto JSON."""
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        arquivo_part = genai.types.Part.from_bytes(data=imagem_bytes, mime_type=mime)
        resposta = client.models.generate_content(
            model=modelo,
            contents=[arquivo_part, PROMPT_USUARIO_CHAMADA],
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_CHAMADA,
                response_mime_type="application/json",
                max_output_tokens=MAX_RESPOSTA_TOKENS,
            ),
        )
    except Exception as erro:
        # A chave nunca entra na mensagem; registra tipo e detalhe do erro do Google
        # (modelo inexistente, chave inválida, rede/TLS bloqueados, cota...).
        logger.warning(
            "Chamada: falha ao chamar o Gemini (modelo=%s): %s: %s",
            modelo,
            type(erro).__name__,
            erro,
        )
        raise LLMError(MENSAGEM_ERRO_PADRAO) from erro

    texto = resposta.text or ""
    if not texto:
        motivo = ""
        candidatos = getattr(resposta, "candidates", None) or []
        if candidatos:
            motivo = str(getattr(candidatos[0], "finish_reason", ""))
        logger.warning(
            "Chamada: Gemini devolveu resposta vazia (modelo=%s, motivo=%s)", modelo, motivo
        )
        raise LLMError(MENSAGEM_ERRO_PADRAO)
    return texto


def _normalizar_confianca(valor) -> float:
    """Garante um float entre 0.0 e 1.0 (padrão 1.0 quando ausente/inválido)."""
    if valor is None or isinstance(valor, bool):
        return 1.0
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 1.0
    return round(max(0.0, min(1.0, numero)), 4)


def _limpar_nomes(itens: list) -> list[dict[str, str | float]]:
    """Extrai apenas nome e confiança, removendo numeração, datas, campos extras e duplicatas."""
    resultado: list[dict[str, str | float]] = []
    vistos: set[str] = set()
    for item in itens:
        if isinstance(item, dict):
            bruto = item.get("nome")
            if item.get("confianca") is None and isinstance(item.get("duvida"), bool):
                # Formato {"nome", "duvida"}: dúvida vira confiança baixa.
                confianca = 0.5 if item["duvida"] else 1.0
            else:
                confianca = _normalizar_confianca(item.get("confianca"))
        elif isinstance(item, str):
            bruto = item
            confianca = 1.0
        else:
            continue

        if not isinstance(bruto, str):
            continue

        limpo = _PREFIXO_NUMERO_RE.sub("", bruto)
        limpo = _DATA_RE.sub("", limpo)
        limpo = re.sub(r"\s+", " ", limpo).strip(" -–—|,;:")
        if not limpo:
            continue

        chave = limpo.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        resultado.append({"nome": limpo, "confianca": confianca})
    return resultado
