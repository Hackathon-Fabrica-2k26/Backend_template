"""Chamada à LLM (Gemini) para gerar o relatório pedagógico do aluno.

Recebe o payload já anonimizado + a api_key e o modelo da Config da escola
do professor, e devolve um dict com a resposta em JSON (radar, pontos
fortes, necessidades, atividades e dica de autonomia).

Qualquer problema de comunicação/resposta da LLM se torna LLMError, que a
view traduz em um 502 com mensagem amigável.
"""

import json
import re

DISCLAIMER = (
    "Este relatório tem finalidade estritamente pedagógica, foi gerado com "
    "apoio de inteligência artificial a partir de informações fornecidas "
    "pelo professor e não constitui diagnóstico. Recomendamos também "
    "consultar os professores e a direção da escola."
)

MODELO_PADRAO = "gemini-2.5-flash"

# Proíbe qualquer tom/estrutura de diagnóstico clínico.
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
    "Não responda nada além do solicitado, caso o usuário tenha pedido um "
    "formato específico (como JSON) será entregue separadamente, caso "
    "contrário responda em texto corrido curto e claro.\n"
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

MAX_RESPOSTA_TOKENS = 8192


class LLMError(Exception):
    """Falha esperada na comunicação ou resposta da LLM."""

    def __init__(self, mensagem: str | None = None):

        super().__init__(
            mensagem or "Não foi possível gerar o relatório agora. Tente novamente em instantes."
        )


def gerar_relatorio(payload: dict, api_key: str, modelo: str = MODELO_PADRAO) -> dict:
    """Gera o relatório pedagógico a partir do payload anonimizado.

    Devolve o dict de resposta com o disclaimer incluído.
    Levanta LLMError se a chamada falhar ou a resposta não for um JSON válido.
    """
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")
    conteudo = FORMATO_RESPOSTA + "\n\n" + json.dumps(payload, ensure_ascii=False)
    try:
        resposta = _pedir_ao_gemini(conteudo, api_key, modelo)
        dados = _extrair_json(resposta)
    except LLMError:
        raise
    except Exception as erro:
        raise LLMError() from erro
    if not isinstance(dados, dict):
        # JSON válido, mas não é o objeto esperado (ex.: lista) — não dá para
        # montar o relatório com ele.
        raise LLMError()
    dados["disclaimer"] = DISCLAIMER
    return dados


def _pedir_ao_gemini(conteudo: str, api_key: str, modelo: str) -> str:
    """Faz a chamada real à API do Gemini e devolve o texto da resposta.

    O import do SDK é adiado para aqui, permitindo testar o serviço com
    a chamada mockada e usá-lo com a api_key da Config da escola.
    """
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
        raise LLMError() from erro
    return resposta.text or ""


def _extrair_json(texto: str) -> dict:
    """Extrai o JSON da resposta, tolerando blocos de código."""
    texto = texto.strip()
    match = re.search(r"\{.*\}", texto, re.DOTALL)
    if match:
        texto = match.group(0)
    try:
        return json.loads(texto)
    except (json.JSONDecodeError, TypeError) as erro:
        raise LLMError() from erro
