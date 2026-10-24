"""Chamada à LLM (Gemini) para gerar relatórios e processar atividades.

Recebe dados pedagógicos, chama o Gemini e devolve respostas estruturadas
em JSON. A extração multimodal processa imagens e PDFs digitalizados
diretamente da memória, sem salvar os arquivos em disco.
"""

import json
import logging
import re
from pathlib import Path

from apps.pedagogico.services.extracao import MAX_TAMANHO_BYTES

from .anonimizar import anonimizar

DISCLAIMER = (
    "Este relatório tem finalidade estritamente pedagógica, foi gerado com "
    "apoio de inteligência artificial a partir de informações fornecidas "
    "pelo professor e não constitui diagnóstico. Recomendamos também "
    "consultar os professores e a direção da escola."
)

logger = logging.getLogger(__name__)

MODELO_PADRAO = "gemini-3.8-flash-lite"

# Proíbe qualquer tom ou estrutura de diagnóstico clínico.
SYSTEM_PROMPT = (
    "Você é um assistente pedagógico. Com base nas informações fornecidas "
    "pelo professor sobre o aluno, gere sugestões práticas de ensino e "
    "acompanhamento de estudos.\n"
    "Você NÃO deve fazer diagnósticos médicos, psiquiátricos ou "
    "psicológicos, nem mencionar ou estimar condições de saúde (por "
    "exemplo: 'probabilidade de TDAH', TDAH, autismo, dislexia, "
    "'deficiência', transtornos, medicação).\n"
    "Fale sempre do aluno pelo codinome informado no contexto (ex.: "
    "'Aluno Alfa'), nunca por nome, e não solicite ou invente dados "
    "pessoais do aluno ou da família.\n"
    "Não responda nada além do solicitado. Caso o usuário tenha pedido um "
    "formato específico, como JSON, entregue-o separadamente; caso "
    "contrário, responda em texto corrido, curto e claro.\n"
    "Seja construtivo, empático e objetivo: destaque pontos fortes, "
    "dificuldades e caminhos práticos de estudo."
)

FORMATO_RESPOSTA = (
    "Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, "
    "no formato:\n"
    "{\n"
    '  "radar": [0-100 para os eixos do acompanhamento do aluno],\n'
    '  "pontos_fortes": ["..."],\n'
    '  "necessidades": ["..."],\n'
    '  "atividades": [{"titulo": "...", "descricao": "..."}],\n'
    '  "dica_de_autonomia": "...",\n'
    '  "observacoes": "..."\n'
    "}\n"
    "Todos os textos em português do Brasil e referindo-se ao aluno pelo "
    "codinome. Use listas vazias quando não houver o que informar e null "
    "quando um campo não se aplicar."
)

FORMATO_SUGESTAO_ATIVIDADE = (
    "Com base no texto pedagógico abaixo, sugira um título curto e uma "
    "descrição/objetivo pedagógico curto em português do Brasil, sem incluir "
    "dados pessoais.\n"
    "Responda APENAS com um JSON válido, sem nenhum texto antes ou depois, "
    "no formato:\n"
    '{\n  "titulo": "...",\n  "descricao": "..."\n}'
)

FORMATO_EXTRACAO_MULTIMODAL = """
Analise o arquivo enviado, que pode ser uma imagem de atividade ou um PDF
digitalizado.

Extraia fielmente todo o texto legível, preservando enunciados, questões,
alternativas, instruções e organização sempre que possível.
Não invente trechos ilegíveis. Se algum conteúdo não puder ser lido,
indique isso de forma breve no texto extraído.

Além disso, sugira um título curto e uma descrição pedagógica objetiva.
Não inclua dados pessoais desnecessários.

Responda APENAS com um JSON válido, sem texto antes ou depois:
{
  "texto_original": "texto extraído do arquivo",
  "titulo": "título da atividade",
  "descricao": "descrição pedagógica"
}
Todos os campos devem ser strings em português do Brasil.
"""

MAX_RESPOSTA_TOKENS = 8192


def normalizar_modelo(modelo: str | None) -> str:
    """Nome do modelo como a API espera: sem espaços nem o prefixo "models/"."""
    nome = (modelo or "").strip()
    if nome.lower().startswith("models/"):
        nome = nome[len("models/") :]
    return nome or MODELO_PADRAO


class LLMError(Exception):
    """Falha esperada na comunicação ou resposta da LLM."""

    def __init__(self, mensagem: str | None = None):
        super().__init__(
            mensagem or "Não foi possível gerar o relatório agora. Tente novamente em instantes."
        )


def gerar_relatorio(
    payload: dict,
    api_key: str,
    modelo: str = MODELO_PADRAO,
) -> dict:
    """Gera o relatório pedagógico a partir do payload anonimizado."""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")

    conteudo = (
        FORMATO_RESPOSTA
        + "\n\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
        )
    )

    try:
        resposta = _pedir_ao_gemini(conteudo, api_key, modelo)
        dados = _extrair_json(resposta)
    except LLMError:
        raise
    except Exception as erro:
        raise LLMError() from erro

    if not isinstance(dados, dict):
        raise LLMError()

    dados["disclaimer"] = DISCLAIMER
    return dados


def sugerir_atividade(
    texto_original: str,
    api_key: str = "",
    nome_arquivo: str = "",
    modelo: str = MODELO_PADRAO,
) -> dict[str, str]:
    """Sugere título e descrição a partir do texto extraído.

    Se a IA falhar ou não houver API key, utiliza um fallback local.
    """
    titulo_fallback = (Path(nome_arquivo).stem.strip() if nome_arquivo else "") or "Atividade"
    titulo_fallback = titulo_fallback[:255]
    descricao_fallback = texto_original.strip()[:300]

    if not api_key:
        return {
            "titulo": titulo_fallback,
            "descricao": descricao_fallback,
        }

    texto_limpo = str(anonimizar({"texto": texto_original}).get("texto", "")).strip()

    conteudo = FORMATO_SUGESTAO_ATIVIDADE + "\n\n" + (texto_limpo or descricao_fallback)

    try:
        resposta = _pedir_ao_gemini(conteudo, api_key, modelo)
        dados = _extrair_json(resposta)

        if not isinstance(dados, dict):
            raise LLMError()

        titulo = str(dados.get("titulo") or "").strip()[:255]
        descricao = str(dados.get("descricao") or "").strip()

        if not titulo or not descricao:
            raise LLMError()

        return {
            "titulo": titulo,
            "descricao": descricao,
        }
    except Exception:
        return {
            "titulo": titulo_fallback,
            "descricao": descricao_fallback,
        }


def extrair_atividade_multimodal(
    conteudo_bytes: bytes,
    mime_type: str,
    api_key: str,
    modelo: str = MODELO_PADRAO,
) -> dict[str, str]:
    """Extrai texto e sugere dados da atividade usando Gemini multimodal."""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")

    if not conteudo_bytes:
        raise LLMError("O arquivo enviado está vazio.")

    if len(conteudo_bytes) > MAX_TAMANHO_BYTES:
        raise LLMError("O arquivo excede o limite máximo de 20 MB.")

    mime_types_permitidos = {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
    }

    if mime_type not in mime_types_permitidos:
        raise LLMError("Tipo de arquivo não permitido para extração multimodal.")

    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=api_key)

        parte_arquivo = types.Part.from_bytes(
            data=conteudo_bytes,
            mime_type=mime_type,
        )

        resposta = cliente.models.generate_content(
            model=modelo,
            contents=[
                parte_arquivo,
                FORMATO_EXTRACAO_MULTIMODAL,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                max_output_tokens=MAX_RESPOSTA_TOKENS,
            ),
        )

        dados = _extrair_json(resposta.text or "")

        if not isinstance(dados, dict):
            raise LLMError()

        campos = ("texto_original", "titulo", "descricao")
        resultado = {campo: str(dados.get(campo) or "").strip() for campo in campos}

        if not all(resultado.values()):
            raise LLMError("A IA não conseguiu extrair todos os dados da atividade.")

        resultado["titulo"] = resultado["titulo"][:255]
        return resultado

    except LLMError:
        raise
    except Exception as erro:
        raise LLMError() from erro


def _pedir_ao_gemini(
    conteudo: str,
    api_key: str,
    modelo: str,
) -> str:
    """Faz a chamada à API do Gemini e devolve o texto da resposta."""
    modelo = normalizar_modelo(modelo)
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        resposta = client.models.generate_content(
            model=modelo,
            contents=conteudo,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                max_output_tokens=MAX_RESPOSTA_TOKENS,
            ),
        )
    except Exception as erro:
        # Nunca registra a chave nem o conteúdo (pode ter dados de alunos).
        logger.warning(
            "Falha ao chamar o Gemini (modelo=%s): %s: %s", modelo, type(erro).__name__, erro
        )
        raise LLMError() from erro

    texto = resposta.text or ""
    if not texto:
        logger.warning("Gemini devolveu resposta vazia (modelo=%s)", modelo)
    return texto


def _extrair_json(texto: str) -> dict:
    """Extrai JSON da resposta, tolerando blocos de código."""
    texto = texto.strip()
    match = re.search(r"\{.*\}", texto, re.DOTALL)

    if match:
        texto = match.group(0)

    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError) as erro:
        raise LLMError() from erro
