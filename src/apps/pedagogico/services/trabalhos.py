import difflib
import io
import json
import os
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile

from apps.alunos.models import Aluno
from apps.alunos.services import alunos_com_consentimento
from apps.escolas.services.escola_usuario import config_ia_do_usuario
from apps.pedagogico.models import Atividade, EnvioTrabalhos, Relatorio, Trabalho
from apps.pedagogico.services.habilidades import (
    NOMES_HABILIDADES,
    filtrar_codigos,
    habilidades_para_prompt,
)
from apps.pedagogico.services.llm import DISCLAIMER, LLMError

TAMANHO_MAXIMO_BYTES = 20 * 1024 * 1024  # 20 MB

FORMATOS_ACEITOS = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}

MIMES_ACEITOS = set(FORMATOS_ACEITOS.values())


def _normalizar_texto(texto: str) -> str:
    """Remove acentos, converte para minúsculas e normaliza espaços."""
    if not texto:
        return ""
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acentos = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sem_acentos.lower().split())


def validar_arquivos_envio(arquivos: list[UploadedFile]) -> list[tuple[str, bytes, str]]:
    """Valida arquivos enviados e retorna lista de (nome_arquivo, conteudo_bytes, mime_type).
    Lança ValueError em caso de arquivo inválido.
    """
    if not arquivos:
        raise ValueError("Envie ao menos um arquivo.")

    processados: list[tuple[str, bytes, str]] = []
    for arq in arquivos:
        nome = arq.name or "arquivo"
        ext = os.path.splitext(nome)[1].lower()
        content_type = getattr(arq, "content_type", "") or ""

        if ext not in FORMATOS_ACEITOS and content_type not in MIMES_ACEITOS:
            raise ValueError(
                f"Formato de arquivo não suportado para '{nome}'. "
                "Formatos aceitos: PDF, PNG, JPG, WEBP e DOCX."
            )

        tamanho = getattr(arq, "size", 0) or 0
        if tamanho > TAMANHO_MAXIMO_BYTES:
            raise ValueError(f"O arquivo '{nome}' excede o tamanho máximo permitido de 20 MB.")

        conteudo = arq.read()
        if len(conteudo) > TAMANHO_MAXIMO_BYTES:
            raise ValueError(f"O arquivo '{nome}' excede o tamanho máximo permitido de 20 MB.")
        if len(conteudo) == 0:
            raise ValueError(f"O arquivo '{nome}' está vazio.")

        mime = FORMATOS_ACEITOS.get(ext) or content_type
        processados.append((nome, conteudo, mime))

    return processados


def extrair_texto_docx(conteudo: bytes) -> str:
    """Extrai o texto de um arquivo .docx em memória sem gravar em disco."""
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            if "word/document.xml" not in zf.namelist():
                return ""
            xml_bytes = zf.read("word/document.xml")
        tree = ET.fromstring(xml_bytes)
        textos = [elem.text for elem in tree.iter() if elem.tag.endswith("}t") and elem.text]
        return " ".join(textos)
    except Exception as exc:
        raise ValueError("Não foi possível ler o arquivo DOCX enviado.") from exc


def _obter_credenciais_llm(usuario) -> tuple[str, str]:
    """Obtém api_key e modelo da Config da escola do professor ou de variáveis de ambiente."""
    config = config_ia_do_usuario(usuario)
    api_key = (
        getattr(config, "api_key", None)
        or getattr(settings, "GEMINI_API_KEY", None)
        or os.environ.get("GEMINI_API_KEY", "")
    )
    modelo = (
        getattr(config, "modelo", None)
        or getattr(settings, "GEMINI_MODEL", None)
        or os.environ.get("GEMINI_MODEL", "gemini-3.8-flash-lite")
    )
    return api_key, modelo


def analisar_trabalho_com_gemini(
    *,
    conteudo: bytes,
    mime_type: str,
    nome_arquivo: str,
    api_key: str,
    modelo: str = "gemini-3.8-flash-lite",
) -> dict[str, Any]:
    """Envia o trabalho em memória para o Gemini extrair o nome do aluno,
    a descrição detalhada da atividade e a análise pedagógica estruturada.
    """
    if not api_key:
        raise LLMError("Chave de API do provedor de IA não configurada.")

    prompt = (
        "Você é um assistente pedagógico de uma professora do 1º ano do Ensino Fundamental.\n"
        "Primeiro, verifique se o arquivo enviado é de fato um trabalho escolar, lição, "
        "exercício ou produção de estudante.\n"
        "Se o arquivo NÃO for um trabalho escolar (por exemplo: documento oficial, "
        "boletim de urna, comprovante, receita médica, panfleto, notícia, meme, etc.), defina "
        "'documento_valido' como false, identifique o 'tipo_documento' e descreva um 'motivo' "
        "curto da recusa em português do Brasil.\n\n"
        "Se for um trabalho escolar válido:\n"
        "Defina 'documento_valido' como true, 'tipo_documento' como 'trabalho escolar', "
        "'motivo' como '', e extraia:\n"
        "1. 'nome_lido': o nome do estudante escrito no trabalho ('' se não houver).\n"
        "2. 'descricao': o que a atividade pede e o que o estudante fez, em poucas frases.\n"
        "3. 'habilidades_demonstradas': códigos da lista abaixo que o estudante mostrou "
        "dominar neste trabalho.\n"
        "4. 'habilidades_a_reforcar': códigos da lista abaixo que este trabalho mostra que "
        "ainda precisam de prática (no máximo 3; lista vazia se não houver evidência clara).\n"
        "5. 'analise_pedagogica': objeto com 'pontos_fortes', 'pontos_de_atencao' e "
        "'sugestoes_para_professora' (listas de frases curtas) e 'observacoes' (texto).\n\n"
        "Use SOMENTE códigos desta lista (habilidades do 1º ano, referência BNCC):\n"
        f"{habilidades_para_prompt()}\n\n"
        "REGRAS:\n"
        "- Descreva o que foi observado NESTE trabalho, sem generalizar sobre a criança.\n"
        "- NUNCA faça diagnóstico nem cite transtornos, CID, laudos ou condições clínicas.\n"
        "- Não use as palavras 'dificuldade', 'déficit' ou 'atraso'; fale em habilidade a "
        "reforçar.\n"
        "- Não repita o nome do estudante fora de 'nome_lido'.\n\n"
        "Responda EXCLUSIVAMENTE com um JSON válido no formato:\n"
        "{\n"
        '  "documento_valido": true,\n'
        '  "tipo_documento": "trabalho escolar",\n'
        '  "motivo": "",\n'
        '  "nome_lido": "...",\n'
        '  "descricao": "...",\n'
        '  "habilidades_demonstradas": ["CODIGO"],\n'
        '  "habilidades_a_reforcar": ["CODIGO"],\n'
        '  "analise_pedagogica": {\n'
        '    "pontos_fortes": ["..."],\n'
        '    "pontos_de_atencao": ["..."],\n'
        '    "sugestoes_para_professora": ["..."],\n'
        '    "observacoes": "..."\n'
        "  }\n"
        "}"
    )

    try:
        from google import genai
        from google.genai import types

        cliente = genai.Client(api_key=api_key)

        if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            texto_docx = extrair_texto_docx(conteudo)
            contents = [f"{prompt}\n\nConteúdo do documento ({nome_arquivo}):\n{texto_docx}"]
        else:
            part = types.Part.from_bytes(data=conteudo, mime_type=mime_type)
            contents = [part, prompt]

        resposta = cliente.models.generate_content(
            model=modelo,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        texto_resposta = getattr(resposta, "text", None)
        if not texto_resposta:
            raise LLMError("Provedor de IA retornou resposta vazia.")
    except LLMError:
        raise
    except Exception as exc:
        raise LLMError("Falha ao comunicar com o provedor de IA.") from exc

    try:
        dados = json.loads(texto_resposta)
    except json.JSONDecodeError as exc:
        raise LLMError("Provedor de IA retornou JSON inválido.") from exc

    if not isinstance(dados, dict):
        raise LLMError("Resposta da IA deve ser um objeto JSON.")

    doc_valido = dados.get("documento_valido")
    if doc_valido is False or str(doc_valido or "").lower() == "false":
        tipo_doc = str(dados.get("tipo_documento") or "outro")
        motivo = str(dados.get("motivo") or "Este arquivo não parece um trabalho escolar.")
        return {
            "documento_valido": False,
            "tipo_documento": tipo_doc,
            "motivo": motivo,
            "nome_lido": "",
            "descricao": motivo,
            "analise_pedagogica": {},
            "habilidades_demonstradas": [],
            "habilidades_a_reforcar": [],
        }

    return {
        "documento_valido": True,
        "tipo_documento": str(dados.get("tipo_documento") or "trabalho escolar"),
        "motivo": "",
        "nome_lido": str(dados.get("nome_lido") or "").strip(),
        "descricao": str(dados.get("descricao") or "").strip(),
        "analise_pedagogica": (
            dados.get("analise_pedagogica")
            if isinstance(dados.get("analise_pedagogica"), dict)
            else {}
        ),
        "habilidades_demonstradas": filtrar_codigos(dados.get("habilidades_demonstradas")),
        "habilidades_a_reforcar": filtrar_codigos(dados.get("habilidades_a_reforcar"), limite=3),
    }


def casar_nome_aluno(
    nome_lido: str,
    alunos: list[Aluno],
) -> tuple[Aluno | None, float, str]:
    """Compara o nome lido com os alunos da turma.
    Retorna (aluno_ou_None, confianca, status_identificacao).
    """
    nome_norm = _normalizar_texto(nome_lido)
    if not nome_norm or not alunos:
        return None, 0.0, Trabalho.IdentificacaoChoices.PENDENTE

    # 1. Casamento exato normalizado
    exatos = [a for a in alunos if _normalizar_texto(a.nome) == nome_norm]
    if len(exatos) == 1:
        return exatos[0], 1.0, Trabalho.IdentificacaoChoices.CONFIRMADA

    # 2. Casamento por primeiro nome ou substring única se não houver ambiguidade
    contidos = [
        a
        for a in alunos
        if nome_norm in _normalizar_texto(a.nome).split()
        or _normalizar_texto(a.nome).startswith(nome_norm + " ")
    ]
    if len(contidos) == 1 and len(nome_norm) >= 3:
        return contidos[0], 0.9, Trabalho.IdentificacaoChoices.PENDENTE

    # 3. Similaridade aproximada (difflib)
    melhor_aluno: Aluno | None = None
    melhor_score = 0.0
    segundo_score = 0.0

    for aluno in alunos:
        score = difflib.SequenceMatcher(None, nome_norm, _normalizar_texto(aluno.nome)).ratio()
        if score > melhor_score:
            segundo_score = melhor_score
            melhor_score = score
            melhor_aluno = aluno
        elif score > segundo_score:
            segundo_score = score

    # Se o score for alto (>= 0.85) e claramente superior ao segundo colocado
    if melhor_aluno and melhor_score >= 0.85 and (melhor_score - segundo_score) >= 0.1:
        return (
            melhor_aluno,
            min(round(melhor_score, 2), 0.99),
            Trabalho.IdentificacaoChoices.PENDENTE,
        )

    # Em caso de dúvida (score intermediário ou ambiguidade), fica pendente
    if melhor_aluno and melhor_score >= 0.5:
        return (
            melhor_aluno,
            round(melhor_score, 2),
            Trabalho.IdentificacaoChoices.PENDENTE,
        )

    return None, round(melhor_score, 2), Trabalho.IdentificacaoChoices.PENDENTE


def _gerar_relatorio_de_trabalho(trabalho: Trabalho) -> Relatorio:
    """Cria um Relatorio do tipo 'atividade' vinculado ao aluno e à atividade."""
    dados_relatorio = {
        "atividade_id": trabalho.atividade.pk,
        "atividade_titulo": trabalho.atividade.titulo,
        "trabalho_id": trabalho.pk,
        "nome_lido": trabalho.nome_lido,
        "descricao": trabalho.descricao_ia,
        "analise_pedagogica": trabalho.dados_analise,
        "habilidades_a_reforcar": [
            {"codigo": c, "nome": NOMES_HABILIDADES[c]}
            for c in trabalho.habilidades_a_reforcar
            if c in NOMES_HABILIDADES
        ],
    }
    return Relatorio.objects.create(
        aluno=trabalho.aluno,
        atividade=trabalho.atividade,
        tipo="atividade",
        disclaimer=DISCLAIMER,
        dados=dados_relatorio,
    )


def processar_envio_trabalhos(
    *,
    atividade: Atividade,
    arquivos: list[UploadedFile],
    usuario,
) -> EnvioTrabalhos:
    """Valida arquivos em memória, analisa cada um com o Gemini, casa com alunos da turma,
    persiste apenas os dados textuais (descartando os arquivos por LGPD) e gera relatórios
    para os trabalhos confirmados.
    """
    arquivos_validados = validar_arquivos_envio(arquivos)
    api_key, modelo = _obter_credenciais_llm(usuario)

    turma = atividade.turma
    alunos_turma = list(Aluno.objects.filter(turma=turma)) if turma else []
    # LGPD (Art. 14): só alunos com consentimento recebem a análise da IA (nomes não vão ao prompt).
    ids_com_consentimento = {a.pk for a in alunos_com_consentimento(alunos_turma)}

    envio = EnvioTrabalhos.objects.create(
        atividade=atividade,
        enviado_por=usuario,
        total_arquivos=len(arquivos_validados),
    )

    for nome_arq, conteudo_bytes, mime_type in arquivos_validados:
        try:
            resultado_ia = analisar_trabalho_com_gemini(
                conteudo=conteudo_bytes,
                mime_type=mime_type,
                nome_arquivo=nome_arq,
                api_key=api_key,
                modelo=modelo,
            )
        finally:
            # Descarte explícito da referência de bytes após análise (LGPD)
            del conteudo_bytes

        doc_valido = resultado_ia.get("documento_valido")
        if doc_valido is False or str(doc_valido or "").lower() == "false":
            motivo = resultado_ia.get("motivo") or "Este arquivo não parece um trabalho escolar."
            tipo_doc = resultado_ia.get("tipo_documento") or "outro"
            Trabalho.objects.create(
                envio=envio,
                atividade=atividade,
                aluno=None,
                identificacao=Trabalho.IdentificacaoChoices.SEM_ALUNO,
                status=Trabalho.StatusChoices.ERRO,
                descricao_ia=motivo,
                dados_analise={
                    "erro": "Este arquivo não parece um trabalho escolar.",
                    "tipo_documento": tipo_doc,
                    "motivo": motivo,
                },
                habilidades_demonstradas=[],
                habilidades_a_reforcar=[],
            )
            continue

        nome_lido = resultado_ia["nome_lido"]
        descricao_ia = resultado_ia["descricao"]
        analise_pedagogica = resultado_ia["analise_pedagogica"]

        aluno_casado, confianca, identificacao = casar_nome_aluno(nome_lido, alunos_turma)

        if aluno_casado and aluno_casado.pk not in ids_com_consentimento:
            # Sem consentimento: descarta a análise e não vincula ao aluno.
            Trabalho.objects.create(
                envio=envio,
                atividade=atividade,
                aluno=None,
                identificacao=Trabalho.IdentificacaoChoices.SEM_CONSENTIMENTO,
                status=Trabalho.StatusChoices.ANALISADO,
            )
            continue

        trabalho = Trabalho.objects.create(
            envio=envio,
            atividade=atividade,
            aluno=aluno_casado,
            nome_lido=nome_lido[:120],
            confianca_nome=confianca,
            identificacao=identificacao,
            confirmado_por=(
                usuario if identificacao == Trabalho.IdentificacaoChoices.CONFIRMADA else None
            ),
            descricao_ia=descricao_ia,
            dados_analise=analise_pedagogica,
            habilidades_demonstradas=resultado_ia.get("habilidades_demonstradas", []),
            habilidades_a_reforcar=resultado_ia.get("habilidades_a_reforcar", []),
            status=Trabalho.StatusChoices.ANALISADO,
        )

        if (
            confianca == 1.0
            and identificacao == Trabalho.IdentificacaoChoices.CONFIRMADA
            and aluno_casado is not None
        ):
            _gerar_relatorio_de_trabalho(trabalho)

    return envio


def confirmar_trabalho(
    *,
    trabalho: Trabalho,
    aluno: Aluno,
    usuario=None,
) -> Trabalho:
    """Confirma manualmente o aluno de um trabalho e gera o relatório se ainda não existir."""
    if trabalho.status == Trabalho.StatusChoices.ERRO:
        raise ValueError("Trabalhos com status de erro não podem ser confirmados.")

    trabalho.aluno = aluno
    trabalho.identificacao = Trabalho.IdentificacaoChoices.CONFIRMADA
    trabalho.confianca_nome = 1.0
    if usuario is not None:
        trabalho.confirmado_por = usuario
    trabalho.save(
        update_fields=[
            "aluno",
            "identificacao",
            "confianca_nome",
            "confirmado_por",
            "updated_at",
        ]
    )

    ja_tem_relatorio = Relatorio.objects.filter(
        aluno=aluno,
        atividade=trabalho.atividade,
        tipo="atividade",
        dados__trabalho_id=trabalho.pk,
    ).exists()

    if not ja_tem_relatorio:
        _gerar_relatorio_de_trabalho(trabalho)

    return trabalho
