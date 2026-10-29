"""Processamento de laudo em memória via Gemini para gerar PerfilApoio (B#44).

Regras de negócio e LGPD:
- O arquivo (PDF, JPG, PNG ou WEBP até 10 MB) é processado exclusivamente em
  memória (bytes) e descartado imediatamente após a leitura da IA.
- Extrai apenas necessidades pedagógicas e estratégias de apoio úteis para a
  sala de aula, sem diagnóstico clínico, CID, remédios, médico ou CRM.
- O nome lido no documento (`nome_no_documento`) é comparado com `aluno.nome`
  sem diferenciar maiúsculas ou acentos (`nome_conferiu: bool`) e descartado.
- Desativa o `PerfilApoio` ativo anterior do aluno e cria um novo ativo.
"""

import logging
import re
import unicodedata
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.alunos.models import Aluno
from apps.pedagogico.models import PerfilApoio
from apps.pedagogico.serializers import PerfilApoioSerializer
from apps.pedagogico.services.llm import (
    MAX_RESPOSTA_TOKENS,
    DocumentoRecusadoError,
    LLMError,
    _extrair_json,
    normalizar_modelo,
)

logger = logging.getLogger(__name__)

TAMANHO_MAXIMO_LAUDO_BYTES = 10 * 1024 * 1024  # 10 MB

MIMES_LAUDO_PERMITIDOS = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "application/pdf": "application/pdf",
}

MENSAGEM_ERRO_LAUDO = (
    "Não foi possível processar o documento enviado agora. Tente novamente em instantes."
)


class NomeNaoConfereError(Exception):
    """Lançada quando o nome no laudo não confere com o do aluno e confirmação não foi dada."""

    def __init__(self, mensagem: str, nome_no_documento: str):
        super().__init__(mensagem)
        self.nome_no_documento = nome_no_documento


SISTEMA_PERFIL = (
    "Você é um assistente pedagógico de apoio a professoras do ensino fundamental.\n"
    "Primeiro, verifique se o arquivo enviado é de fato um laudo ou relatório de saúde "
    "ou de acompanhamento do estudante (laudo médico, psicológico, psicopedagógico, "
    "neurológico, fonoaudiológico ou plano de AEE/Atendimento Educacional Especializado).\n"
    "Se o documento NÃO for um laudo ou relatório de saúde/AEE (por exemplo: boletim de urna, "
    "documento pessoal, comprovante, panfleto, notícia, atividade escolar, texto genérico, etc.), "
    "defina `documento_valido` como false, identifique o `tipo_documento` e descreva "
    "brevemente o `motivo` da recusa em português do Brasil.\n\n"
    "Se for um laudo ou relatório de acompanhamento de saúde/AEE válido:\n"
    "Defina `documento_valido` como true, `tipo_documento` como 'laudo', `motivo` como '', e "
    "extraia APENAS necessidades pedagógicas e estratégias de apoio úteis para a sala de aula, "
    "em frases curtas e neutras.\n"
    "Nunca faça diagnóstico, nunca mencione condições de saúde, remédios, CID ou médicos.\n"
    "Responda SOMENTE com JSON válido, em português do Brasil."
)

PROMPT_PERFIL = (
    "Verifique se o anexo (foto, imagem ou PDF) é um laudo ou relatório de "
    "acompanhamento de saúde/AEE.\n"
    "Se NÃO for, retorne:\n"
    '{"documento_valido": false, "tipo_documento": "...", "motivo": "...", '
    '"nome_no_documento": "", "necessidades": [], "estrategias": [], "observacoes": ""}\n\n'
    "Se for válido, extraia APENAS necessidades pedagógicas e estratégias de apoio úteis "
    "para a sala de aula, em frases curtas e neutras. NÃO escreva diagnóstico, sigla de condição, "
    "CID, remédio, nome de médico ou CRM, e NÃO escreva o nome da criança em \"necessidades\", "
    '"estrategias" nem "observacoes".\n'
    'Devolva o nome que consta no documento só no campo "nome_no_documento" '
    "(será usado apenas para conferência e descartado).\n"
    'Formato:\n{"documento_valido": true, "tipo_documento": "laudo", "motivo": "", '
    '"nome_no_documento": "...", "necessidades": ["..."], "estrategias": ["..."], '
    '"observacoes": "..."}'
)

DIAGNOSTICO = re.compile(
    r"\b("
    r"tea|tdah|tdh|autis\w*|d[eé]ficit|hiperativ\w*|disl[eé]x\w*|transtorn\w*|"
    r"diagn[oó]st\w*|s[ií]ndrome|espectro|defici[eê]ncia|medica\w*|laudo|cid|cid-10|"
    r"neuro\w*|psiquiatr\w*|crm|dr\.?|dra\.?|risperidona|ritalina|metilfenidato|"
    r"concerta|venvanse|fluoxetina|sertralina"
    r")\b",
    re.IGNORECASE,
)
CID = re.compile(r"\b[A-Z]\d{2}(?:\.\d)?\b")


def _normalizar_nome(texto: str) -> str:
    """Normaliza um nome para comparação sem diferenciar acentos, pontuação ou caixa."""
    decomposto = unicodedata.normalize("NFD", str(texto or "").lower())
    sem_acentos = "".join(c for c in decomposto if unicodedata.category(c) != "Mn")
    apenas_alfanum = re.sub(r"[^a-z0-9 ]", " ", sem_acentos)
    return re.sub(r"\s+", " ", apenas_alfanum).strip()


def _conferir_nome_documento(nome_no_documento: str, nome_aluno: str) -> bool:
    """Compara o nome extraído do documento com o nome do aluno sem diferenciar acentos/caixa."""
    doc_norm = _normalizar_nome(nome_no_documento)
    aluno_norm = _normalizar_nome(nome_aluno)
    if not doc_norm or not aluno_norm:
        return False
    return doc_norm == aluno_norm


def _tokens_nomes_proibidos(*nomes: str) -> list[str]:
    """Extrai nomes completos e partes com pelo menos 3 letras para bloquear vazamento de nome."""
    proibidos: list[str] = []
    for nome in nomes:
        norm = _normalizar_nome(nome)
        if not norm:
            continue
        proibidos.append(norm)
        for parte in norm.split():
            if len(parte) >= 3 and parte not in proibidos:
                proibidos.append(parte)
    return proibidos


def _item_tem_vazamento(texto: str, nomes_proibidos: list[str]) -> bool:
    """Indica se um item contém CID, diagnóstico/remédio/médico ou nome da criança."""
    if DIAGNOSTICO.search(texto) or CID.search(texto):
        return True
    texto_norm = _normalizar_nome(texto)
    for token in nomes_proibidos:
        if re.search(rf"\b{re.escape(token)}\b", texto_norm):
            return True
    return False


def _filtrar_lista_pedagogica(itens: Any, nomes_proibidos: list[str]) -> list[str]:
    """Remove itens vazios, duplicados ou que casem com as regex DIAGNOSTICO, CID ou nome."""
    if not isinstance(itens, list):
        return []
    limpos: list[str] = []
    vistos: set[str] = set()
    for item in itens:
        if not isinstance(item, str):
            continue
        texto = re.sub(r"\s+", " ", item).strip()
        if not texto:
            continue
        if _item_tem_vazamento(texto, nomes_proibidos):
            continue
        chave = texto.casefold()
        if chave in vistos:
            continue
        vistos.add(chave)
        limpos.append(texto)
    return limpos


def _filtrar_observacoes(observacoes: Any, nomes_proibidos: list[str]) -> str:
    """Remove de `observacoes` qualquer sentença que case com DIAGNOSTICO, CID ou nome."""
    if not isinstance(observacoes, str):
        return ""
    texto = re.sub(r"\s+", " ", observacoes).strip()
    if not texto:
        return ""
    sentencas = re.split(r"(?<=[\.\!\?\;])\s+", texto)
    aprovadas = [
        sentenca.strip()
        for sentenca in sentencas
        if sentenca.strip() and not _item_tem_vazamento(sentenca, nomes_proibidos)
    ]
    return " ".join(aprovadas).strip()


def _pedir_laudo_ao_gemini(
    arquivo_bytes: bytes,
    mime: str,
    api_key: str,
    modelo: str,
) -> str:
    """Envia o laudo em memória ao Gemini e devolve o texto JSON da resposta."""
    try:
        from google import genai

        client = genai.Client(api_key=api_key)
        arquivo_part = genai.types.Part.from_bytes(data=arquivo_bytes, mime_type=mime)
        resposta = client.models.generate_content(
            model=modelo,
            contents=[arquivo_part, PROMPT_PERFIL],
            config=genai.types.GenerateContentConfig(
                system_instruction=SISTEMA_PERFIL,
                response_mime_type="application/json",
                max_output_tokens=MAX_RESPOSTA_TOKENS,
            ),
        )
    except Exception as erro:
        # Nunca registra a chave nem o conteúdo do arquivo/laudo.
        logger.warning(
            "Laudo: falha ao chamar o Gemini (modelo=%s): %s: %s",
            modelo,
            type(erro).__name__,
            erro,
        )
        raise LLMError(MENSAGEM_ERRO_LAUDO) from erro

    texto = resposta.text or ""
    if not texto:
        motivo = ""
        candidatos = getattr(resposta, "candidates", None) or []
        if candidatos:
            motivo = str(getattr(candidatos[0], "finish_reason", ""))
        logger.warning(
            "Laudo: Gemini devolveu resposta vazia (modelo=%s, motivo=%s)",
            modelo,
            motivo,
        )
        raise LLMError(MENSAGEM_ERRO_LAUDO)
    return texto


def processar_laudo(
    aluno: Aluno,
    arquivo_bytes: bytes,
    mime: str,
    config,
    confirmar_nome: bool = False,
) -> dict[str, Any]:
    """Processa o laudo em memória, atualiza o PerfilApoio ativo e descarta o arquivo.

    Retorna ``{perfil_apoio, nome_conferiu, arquivo_excluido_em}``.
    """
    if not arquivo_bytes:
        raise LLMError("O arquivo enviado está vazio.")
    if len(arquivo_bytes) > TAMANHO_MAXIMO_LAUDO_BYTES:
        raise LLMError("O arquivo deve ter no máximo 10 MB.")

    mime_normalizado = MIMES_LAUDO_PERMITIDOS.get((mime or "").lower().strip())
    if mime_normalizado is None:
        raise LLMError("Formato inválido. Envie um arquivo PDF, JPG, PNG ou WEBP.")

    api_key = getattr(config, "api_key", "") if config is not None else ""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")
    modelo = normalizar_modelo(getattr(config, "modelo", "") if config is not None else "")

    try:
        try:
            resposta = _pedir_laudo_ao_gemini(arquivo_bytes, mime_normalizado, api_key, modelo)
        except LLMError:
            raise
        except Exception as erro:
            logger.warning(
                "Laudo: erro inesperado ao chamar o Gemini (modelo=%s): %s: %s",
                modelo,
                type(erro).__name__,
                erro,
            )
            raise LLMError(MENSAGEM_ERRO_LAUDO) from erro
    finally:
        # Garante descarte explícito dos bytes do arquivo e registra o instante da exclusão.
        del arquivo_bytes
        arquivo_excluido_em = timezone.now().isoformat()

    try:
        dados = _extrair_json(resposta)
    except Exception as erro:
        logger.warning(
            "Laudo: resposta do Gemini não é JSON válido (modelo=%s, %d caracteres)",
            modelo,
            len(resposta),
        )
        raise LLMError(MENSAGEM_ERRO_LAUDO) from erro

    if not isinstance(dados, dict):
        logger.warning("Laudo: JSON do Gemini não é um objeto (modelo=%s)", modelo)
        raise LLMError(MENSAGEM_ERRO_LAUDO)

    doc_valido = dados.get("documento_valido")
    if doc_valido is False or str(doc_valido or "").lower() == "false":
        tipo_doc = str(dados.get("tipo_documento") or "outro")
        motivo_padrao = "O arquivo enviado não parece um laudo ou relatório de acompanhamento."
        motivo = str(dados.get("motivo") or motivo_padrao)
        raise DocumentoRecusadoError(
            "Este arquivo não parece um laudo ou relatório de acompanhamento.",
            tipo_documento=tipo_doc,
            motivo=motivo,
        )

    nome_no_documento = str(dados.get("nome_no_documento") or "").strip()
    nome_conferiu = _conferir_nome_documento(nome_no_documento, aluno.nome)

    if not nome_conferiu and not confirmar_nome:
        raise NomeNaoConfereError(
            "O nome no documento não confere com o do aluno.",
            nome_no_documento=nome_no_documento,
        )

    nomes_proibidos = _tokens_nomes_proibidos(aluno.nome, nome_no_documento)
    # Descarta o nome lido do documento (nunca persiste nem retorna).
    del nome_no_documento

    necessidades = _filtrar_lista_pedagogica(dados.get("necessidades"), nomes_proibidos)
    estrategias = _filtrar_lista_pedagogica(dados.get("estrategias"), nomes_proibidos)
    observacoes = _filtrar_observacoes(dados.get("observacoes"), nomes_proibidos)

    with transaction.atomic():
        PerfilApoio.objects.filter(aluno=aluno, ativo=True).update(ativo=False)
        novo_perfil = PerfilApoio.objects.create(
            aluno=aluno,
            necessidades=necessidades,
            estrategias=estrategias,
            observacoes=observacoes,
            ativo=True,
        )

    return {
        "perfil_apoio": PerfilApoioSerializer(novo_perfil).data,
        "nome_conferiu": nome_conferiu,
        "arquivo_excluido_em": arquivo_excluido_em,
    }
