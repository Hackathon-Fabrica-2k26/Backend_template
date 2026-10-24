"""Serviço de processamento e análise de trabalhos escolares via Gemini (LGPD).

Os arquivos são processados exclusivamente em memória e descartados imediatamente.
Nenhum arquivo ou imagem é salvo em disco ou banco de dados.
"""

import difflib
import io
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from rest_framework.exceptions import ValidationError

from apps.pedagogico.models import Atividade, EnvioTrabalhos, Relatorio, Trabalho
from apps.pedagogico.services.llm import (
    MAX_RESPOSTA_TOKENS,
    MODELO_PADRAO,
    LLMError,
    _extrair_json,
)

TAMANHO_MAXIMO_BYTES = 20 * 1024 * 1024  # 20 MB

MIMES_PERMITIDOS = {
    "application/pdf": "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    ),
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
}

EXTENSOES_PERMITIDAS = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}

SYSTEM_PROMPT_TRABALHO = (
    "Você é um assistente pedagógico especializado na avaliação e análise de produções "
    "escolares de anos iniciais do Ensino Fundamental.\n"
    "Analise o trabalho escolar fornecido e extraia:\n"
    "1. O nome do aluno/estudante que realizou a atividade (cabeçalho, assinatura ou folha).\n"
    "2. Uma descrição pedagógica detalhada do que a criança produziu.\n"
    "3. Uma análise pedagógica objetiva com pontos fortes e habilidades observadas.\n\n"
    "Regras obrigatórias:\n"
    '- Se o nome do estudante não estiver legível ou não constar, devolva "" (string vazia).\n'
    "- Responda EXCLUSIVAMENTE com um JSON válido no formato:\n"
    "{\n"
    '  "nome_lido": "Nome do estudante ou """,\n'
    '  "descricao": "Descrição pedagógica do trabalho...",\n'
    '  "analise_pedagogica": {\n'
    '    "pontos_fortes": ["..."],\n'
    '    "habilidades_observadas": ["..."],\n'
    '    "observacoes": "..."\n'
    "  }\n"
    "}"
)

PROMPT_USUARIO_TRABALHO = (
    "Analise este trabalho escolar e devolva exclusivamente o JSON com nome_lido, "
    "descricao e analise_pedagogica."
)


def normalizar_texto(texto: str) -> str:
    """Remove acentuação, caracteres especiais e converte para minúsculas."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    sem_pontuacao = re.sub(r"[^\w\s]", " ", sem_acento.lower())
    return re.sub(r"\s+", " ", sem_pontuacao).strip()


def extrair_texto_docx(docx_bytes: bytes) -> str:
    """Extrai texto de arquivo DOCX em memória sem dependências externas."""
    import zipfile

    try:
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            xml_content = z.read("word/document.xml")
        tree = ET.fromstring(xml_content)
        namespaces = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        textos = [node.text for node in tree.iterfind(".//w:t", namespaces) if node.text]
        return "\n".join(textos).strip()
    except Exception as erro:
        raise ValidationError(f"Não foi possível ler o arquivo DOCX: {erro}") from erro


def validar_arquivo(arquivo) -> tuple[bytes, str]:
    """Valida tamanho e formato do arquivo e retorna os bytes lidos e o MIME type."""
    tamanho = getattr(arquivo, "size", 0)
    if tamanho <= 0:
        raise ValidationError("O arquivo enviado está vazio.")
    if tamanho > TAMANHO_MAXIMO_BYTES:
        raise ValidationError("O arquivo ultrapassa o tamanho máximo permitido de 20 MB.")

    nome_arquivo = getattr(arquivo, "name", "") or ""
    extensao = Path(nome_arquivo).suffix.lower()
    content_type = (getattr(arquivo, "content_type", "") or "").lower().strip()

    mime = MIMES_PERMITIDOS.get(content_type)
    if mime is None and content_type in ("", "application/octet-stream"):
        mime = EXTENSOES_PERMITIDAS.get(extensao)

    if mime is None or (extensao and extensao not in EXTENSOES_PERMITIDAS):
        raise ValidationError(
            f"Formato inválido ({extensao or content_type}). "
            "Envie arquivos nos formatos PDF, DOCX, JPG ou PNG."
        )

    conteudo = arquivo.read()
    return conteudo, mime


def obter_alunos_da_atividade(atividade: Atividade) -> list:
    """Recupera a lista de alunos da turma da atividade (compatível com B#39)."""
    # 1. Se a atividade já tiver relação direta com Turma (B#39)
    turma = getattr(atividade, "turma", None)
    if turma is not None and hasattr(turma, "alunos"):
        return list(turma.alunos.filter(deleted__isnull=True))

    # 2. Relação via atividade.aluno.turma
    aluno = getattr(atividade, "aluno", None)
    if aluno is not None and getattr(aluno, "turma", None) is not None:
        return list(aluno.turma.alunos.filter(deleted__isnull=True))

    # 3. Fallback para aluno único da atividade
    if aluno is not None and getattr(aluno, "deleted", None) is None:
        return [aluno]

    return []


def professor_tem_acesso(usuario, atividade: Atividade) -> bool:
    """Verifica se o usuário é professor da turma da atividade."""
    if usuario.is_staff or usuario.is_superuser:
        return True

    turma = getattr(atividade, "turma", None)
    if turma is not None and hasattr(turma, "professores"):
        if turma.professores.filter(pk=usuario.pk).exists():
            return True

    aluno = getattr(atividade, "aluno", None)
    if aluno is not None and getattr(aluno, "turma", None) is not None:
        if aluno.turma.professores.filter(pk=usuario.pk).exists():
            return True

    return False


def casar_nome_aluno(nome_lido: str, alunos: list) -> tuple[Any, float, str]:
    """Compara o nome lido com a lista de alunos da turma calculando a confiança.

    Retorna: (aluno_casado, confianca, identificacao)
    """
    norm_lido = normalizar_texto(nome_lido)
    if not norm_lido or not alunos:
        return None, 0.0, Trabalho.IdentificacaoChoices.PENDENTE

    tokens_lido = set(norm_lido.split())
    pontuacoes: list[tuple[float, Any]] = []

    for aluno in alunos:
        norm_aluno = normalizar_texto(aluno.nome)
        if not norm_aluno:
            continue

        # 1. Casamento exato
        if norm_lido == norm_aluno:
            return aluno, 1.0, Trabalho.IdentificacaoChoices.CONFIRMADA

        # 2. Similaridade de sequência
        ratio = difflib.SequenceMatcher(None, norm_lido, norm_aluno).ratio()

        # 3. Similaridade por palavras/tokens
        tokens_aluno = set(norm_aluno.split())
        intersecao = tokens_lido.intersection(tokens_aluno)
        if intersecao:
            token_ratio = len(intersecao) / max(len(tokens_lido), 1)
            # Se todos os tokens lidos estão no nome do aluno (ex: "Lucas" em "Lucas Silva")
            if token_ratio == 1.0:
                ratio = max(ratio, 0.90)
            else:
                ratio = max(ratio, 0.5 + 0.4 * token_ratio)

        pontuacoes.append((ratio, aluno))

    pontuacoes.sort(key=lambda x: x[0], reverse=True)
    if not pontuacoes:
        return None, 0.0, Trabalho.IdentificacaoChoices.PENDENTE

    melhor_score, melhor_aluno = pontuacoes[0]
    melhor_score = round(float(melhor_score), 2)

    # Verifica ambiguidade se houver múltiplos alunos com pontuação próxima
    segundo_score = pontuacoes[1][0] if len(pontuacoes) > 1 else 0.0
    ambiguo = (melhor_score - segundo_score) < 0.15 and segundo_score >= 0.70

    if melhor_score >= 0.85 and not ambiguo:
        return melhor_aluno, melhor_score, Trabalho.IdentificacaoChoices.CONFIRMADA

    if melhor_score >= 0.50:
        return melhor_aluno, melhor_score, Trabalho.IdentificacaoChoices.PENDENTE

    return None, melhor_score, Trabalho.IdentificacaoChoices.PENDENTE


def analisar_trabalho_com_gemini(
    conteudo_bytes: bytes,
    mime: str,
    api_key: str,
    modelo: str = MODELO_PADRAO,
) -> dict:
    """Envia o conteúdo do trabalho em memória ao Gemini e devolve o JSON estruturado."""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")

    try:
        from google import genai

        client = genai.Client(api_key=api_key)

        if mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            texto_docx = extrair_texto_docx(conteudo_bytes)
            conteudo_prompt = f"{PROMPT_USUARIO_TRABALHO}\n\nConteúdo do documento:\n{texto_docx}"
            contents = [conteudo_prompt]
        else:
            part = genai.types.Part.from_bytes(data=conteudo_bytes, mime_type=mime)
            contents = [part, PROMPT_USUARIO_TRABALHO]

        resposta = client.models.generate_content(
            model=modelo or MODELO_PADRAO,
            contents=contents,
            config=genai.types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT_TRABALHO,
                response_mime_type="application/json",
                max_output_tokens=MAX_RESPOSTA_TOKENS,
            ),
        )
        dados = _extrair_json(resposta.text or "{}")
        if not isinstance(dados, dict):
            raise LLMError("Resposta da IA em formato inválido.")
        return dados
    except LLMError:
        raise
    except Exception as erro:
        raise LLMError(f"Falha na comunicação com o Gemini: {erro}") from erro


def processar_envio_trabalhos(atividade: Atividade, usuario, arquivos: list) -> EnvioTrabalhos:
    """Processa o lote de arquivos em memória, analisa com IA e grava Trabalhos e Relatórios."""
    if not arquivos:
        raise ValidationError({"arquivos": "Envie pelo menos um arquivo de trabalho."})

    # Validar todos os arquivos primeiro
    arquivos_validados: list[tuple[bytes, str]] = []
    for arq in arquivos:
        conteudo, mime = validar_arquivo(arq)
        arquivos_validados.append((conteudo, mime))

    envio = EnvioTrabalhos.objects.create(
        atividade=atividade,
        enviado_por=usuario,
        total_arquivos=len(arquivos_validados),
        status=EnvioTrabalhos.StatusChoices.PROCESSANDO,
    )

    alunos_turma = obter_alunos_da_atividade(atividade)
    config = getattr(getattr(usuario, "escola", None), "config", None)
    api_key = getattr(config, "api_key", "") if config else ""
    modelo = (getattr(config, "modelo", "") if config else "") or MODELO_PADRAO

    todos_confirmados = True

    try:
        for conteudo_bytes, mime in arquivos_validados:
            resultado_ia = analisar_trabalho_com_gemini(conteudo_bytes, mime, api_key, modelo)
            nome_lido = str(resultado_ia.get("nome_lido", "") or "").strip()
            descricao_ia = str(resultado_ia.get("descricao", "") or "").strip()
            analise_pedagogica = resultado_ia.get("analise_pedagogica")
            if not isinstance(analise_pedagogica, dict):
                analise_pedagogica = {}

            aluno, confianca, identificacao = casar_nome_aluno(nome_lido, alunos_turma)

            trabalho = Trabalho.objects.create(
                envio=envio,
                atividade=atividade,
                aluno=aluno,
                nome_lido=nome_lido,
                confianca=confianca,
                identificacao=identificacao,
                descricao_ia=descricao_ia,
                analise_pedagogica=analise_pedagogica,
            )

            if identificacao == Trabalho.IdentificacaoChoices.CONFIRMADA and aluno is not None:
                gravar_relatorio_atividade(trabalho)
            else:
                todos_confirmados = False
    except Exception:
        # Garante que referências a bytes sejam limpas
        del arquivos_validados
        raise

    del arquivos_validados

    if todos_confirmados and envio.trabalhos.exists():
        envio.status = EnvioTrabalhos.StatusChoices.CONCLUIDO
    else:
        envio.status = EnvioTrabalhos.StatusChoices.REVISAO_PENDENTE
    envio.save(update_fields=["status"])

    return envio


def gravar_relatorio_atividade(trabalho: Trabalho) -> Relatorio:
    """Cria o Relatorio pedagógico de atividade para o aluno e vincula à Atividade."""
    relatorio = Relatorio.objects.create(
        aluno=trabalho.aluno,
        tipo="atividade",
        dados={
            "descricao": trabalho.descricao_ia,
            "analise_pedagogica": trabalho.analise_pedagogica,
            "atividade_id": trabalho.atividade_id,
            "atividade_nome": trabalho.atividade.nome,
            "trabalho_id": trabalho.id,
        },
    )
    trabalho.atividade.relatorios.add(relatorio)
    return relatorio


def confirmar_trabalho(
    trabalho: Trabalho,
    aluno,
    identificacao: str = Trabalho.IdentificacaoChoices.CONFIRMADA,
) -> Trabalho:
    """Confirma ou atribui manualmente o aluno a um Trabalho e gera o Relatorio."""
    trabalho.aluno = aluno
    trabalho.identificacao = identificacao
    if identificacao == Trabalho.IdentificacaoChoices.MANUAL:
        trabalho.confianca = 1.0
    trabalho.save(update_fields=["aluno", "identificacao", "confianca", "updated_at"])

    gravar_relatorio_atividade(trabalho)

    # Recalcula status do envio
    envio = trabalho.envio
    if not envio.trabalhos.filter(identificacao=Trabalho.IdentificacaoChoices.PENDENTE).exists():
        envio.status = EnvioTrabalhos.StatusChoices.CONCLUIDO
        envio.save(update_fields=["status", "updated_at"])

    return trabalho
