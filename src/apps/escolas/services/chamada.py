"""Reconhecimento de nomes de alunos em foto de lista de chamada via Gemini (OCR).

A imagem é processada exclusivamente em memória (bytes) e nunca é gravada em
disco, banco de dados ou logs (LGPD).
"""

import re

from apps.pedagogico.services.llm import (
    MAX_RESPOSTA_TOKENS,
    MODELO_PADRAO,
    LLMError,
    _extrair_json,
)

MENSAGEM_ERRO_PADRAO = (
    "Não foi possível reconhecer os nomes na imagem agora. Tente novamente em instantes."
)

SYSTEM_PROMPT_CHAMADA = (
    "Você é um assistente de OCR escolar. Analise a imagem de uma lista de "
    "chamada e extraia apenas os nomes completos dos estudantes listados.\n"
    "Regras obrigatórias:\n"
    "- Mantenha exatamente a ordem em que os nomes aparecem na lista.\n"
    "- Remova números de chamada, códigos de matrícula, datas, cabeçalhos, "
    "assinaturas, notas ou marcações de presença/falta.\n"
    "- Não inclua nomes duplicados.\n"
    "- Não invente nomes que não estejam legíveis na imagem.\n"
    '- Responda APENAS com um JSON válido no formato {"nomes": ["Nome Completo 1", ...]}.'
)

PROMPT_USUARIO_CHAMADA = (
    "Extraia os nomes completos dos alunos desta lista de chamada e devolva "
    'exclusivamente um JSON no formato {"nomes": ["..."]}.'
)

_PREFIXO_NUMERO_RE = re.compile(r"^\s*\d+\s*[\.\)\-–—:ºª]*\s*")


def reconhecer_nomes(imagem_bytes: bytes, mime: str, config) -> list[str]:
    """Envia a imagem da lista de chamada ao Gemini e devolve a lista de nomes.

    Recebe os bytes da imagem em memória, o MIME type validado e a ``Config``
    da escola do professor. Levanta ``LLMError`` se não houver credencial
    configurada ou se a chamada/resposta da LLM falhar.
    """
    api_key = getattr(config, "api_key", "") if config is not None else ""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")
    modelo = (getattr(config, "modelo", "") if config is not None else "") or MODELO_PADRAO

    try:
        resposta = _pedir_ocr_ao_gemini(imagem_bytes, mime, api_key, modelo)
        dados = _extrair_json(resposta)
    except LLMError as erro:
        raise LLMError(MENSAGEM_ERRO_PADRAO) from erro
    except Exception as erro:
        raise LLMError(MENSAGEM_ERRO_PADRAO) from erro

    if not isinstance(dados, dict) or not isinstance(dados.get("nomes"), list):
        raise LLMError(MENSAGEM_ERRO_PADRAO)

    return _limpar_nomes(dados["nomes"])


def _pedir_ocr_ao_gemini(imagem_bytes: bytes, mime: str, api_key: str, modelo: str) -> str:
    """Envia a imagem em memória ao Gemini Vision e devolve o texto JSON."""
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        imagem_part = genai.types.Part.from_bytes(data=imagem_bytes, mime_type=mime)
        resposta = client.models.generate_content(
            model=modelo,
            contents=[imagem_part, PROMPT_USUARIO_CHAMADA],
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_CHAMADA,
                response_mime_type="application/json",
                max_output_tokens=MAX_RESPOSTA_TOKENS,
            ),
        )
    except Exception as erro:
        raise LLMError(MENSAGEM_ERRO_PADRAO) from erro
    return resposta.text or ""


def _limpar_nomes(itens: list) -> list[str]:
    """Remove numeração inicial, espaços extras, itens vazios e duplicatas preservando a ordem."""
    nomes: list[str] = []
    vistos: set[str] = set()
    for item in itens:
        if not isinstance(item, str):
            continue
        limpo = _PREFIXO_NUMERO_RE.sub("", item).strip()
        limpo = re.sub(r"\s+", " ", limpo)
        if not limpo:
            continue
        chave = limpo.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        nomes.append(limpo)
    return nomes
