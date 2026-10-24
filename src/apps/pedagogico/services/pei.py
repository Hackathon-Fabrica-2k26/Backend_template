"""Serviço sob demanda de geração de rascunho de PEI (Plano Educacional Individualizado) e PDF.

Regras de negócio e LGPD (B#46):
- Calculado sob demanda (não cria model nem migração, e nada é persistido no banco).
- Reúne o PerfilApoio ativo (necessidades/estratégias), os Relatorios e as
  `descricao_ia` dos Trabalhos analisados do aluno.
- Anonimiza todos os textos (removendo nome do aluno, responsável, turma, datas,
  CPF, CID e termos clínicos) antes de enviar ao Gemini.
- Solicita um rascunho estruturado
  `{objetivos, adaptacoes, estrategias, acompanhamento, observacoes}`
  em linguagem estritamente pedagógica, sem diagnóstico clínico.
- Inclui obrigatoriamente o aviso ético:
  "Rascunho para revisão da professora e da coordenação; não substitui o PEI oficial."
- Gera PDF em memória com reportlab sem CPF e sem dados do responsável.
"""

import json
import re
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

from apps.alunos.models import Aluno
from apps.pedagogico.models import PerfilApoio, Relatorio, Trabalho

from .anonimizar import anonimizar
from .llm import (
    MODELO_PADRAO,
    LLMError,
    _extrair_json,
    _pedir_ao_gemini,
)

DISCLAIMER_PEI = (
    "Rascunho para revisão da professora e da coordenação; não substitui o PEI oficial."
)

CID_RE = re.compile(r"\b(?:CID(?:-\d+)?\s*)?[A-Z]\d{2}(?:\.\d+)?\b", re.IGNORECASE)
DATA_CURTA_RE = re.compile(r"\b(?:\d{1,2}/\d{1,2}/\d{2,4}|\d{4}-\d{2}-\d{2})\b")
TERMOS_CLINICOS_RE = re.compile(
    r"\b("
    r"tdah|tea|autismo|autista|dislexia|disl[eé]xic[oa]|discalculia|disgrafia|"
    r"tod|transtorno[s]?|s[ií]ndrome[s]?|defici[eê]ncia[s]?|laudo[s]?|"
    r"diagn[oó]stico[s]?|psiqui[aá]tric[oa][s]?|neurol[oó]gic[oa][s]?|"
    r"medica[cç][aã]o|medicamento[s]?|ritalina|superdota[cç][aã]o|altas\s+habilidades"
    r")\b",
    re.IGNORECASE,
)

PROMPT_RASCUNHO_PEI = (
    "Você receberá informações pedagógicas anonimizadas de um estudante "
    "(perfil de apoio com necessidades e estratégias pedagógicas, síntese de "
    "relatórios pedagógicos e descrições de trabalhos realizados).\n"
    "Elabore um RASCUNHO estruturado de PEI (Plano Educacional Individualizado) "
    "em português do Brasil para apoiar a professora e a coordenação.\n"
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Use linguagem estritamente pedagógica, acolhedora e construtiva.\n"
    "2. NUNCA emita diagnóstico médico, psicológico ou clínico, NUNCA cite "
    "código CID, transtornos, síndromes, laudos médicos ou medicação.\n"
    "3. Não invente nomes próprios, datas ou dados familiares.\n\n"
    "Responda APENAS com um JSON válido, sem texto antes ou depois, no formato:\n"
    "{\n"
    '  "objetivos": ["Objetivo pedagógico 1", "Objetivo pedagógico 2"],\n'
    '  "adaptacoes": ["Adaptação curricular/ambiental 1"],\n'
    '  "estrategias": ["Estratégia didática e de mediação 1"],\n'
    '  "acompanhamento": ["Critério/forma de acompanhamento 1"],\n'
    '  "observacoes": "Síntese pedagógica geral para revisão da equipe escolar."\n'
    "}"
)


def _limpar_texto_clinico(texto: str) -> str:
    """Remove menções a CID e termos clínicos/diagnósticos de uma string."""
    limpo = CID_RE.sub("", texto)
    limpo = TERMOS_CLINICOS_RE.sub("", limpo)
    limpo = re.sub(r"\s{2,}", " ", limpo)
    limpo = re.sub(r"(?:[,;:/-]\s*){2,}", "", limpo)
    return limpo.strip(" ,;:-")


def _anonimizar_texto_aluno(
    texto: str,
    nome_aluno: str,
    nome_responsavel: str,
    nome_turma: str,
) -> str:
    """Anonimiza um texto removendo nome do aluno, responsável, turma, datas e termos clínicos."""
    if not texto or not texto.strip():
        return ""
    anon = anonimizar(
        {"texto": texto},
        nome_aluno=nome_aluno,
        nome_responsavel=nome_responsavel,
    )
    resultado = str(anon.get("texto") or "")
    codinome = str(anon.get("codinome_aluno") or "")
    if codinome:
        resultado = re.sub(
            rf"\b{re.escape(codinome)}\b",
            "o estudante",
            resultado,
            flags=re.IGNORECASE,
        )

    if nome_turma and len(nome_turma.strip()) > 1:
        resultado = re.sub(
            rf"\b{re.escape(nome_turma.strip())}\b",
            "",
            resultado,
            flags=re.IGNORECASE,
        )

    resultado = DATA_CURTA_RE.sub("", resultado)
    resultado = _limpar_texto_clinico(resultado)
    return resultado.strip()


def _normalizar_lista_strings(valor: Any) -> list[str]:
    """Converte o valor retornado pela IA em uma lista limpa de strings pedagógicas."""
    if isinstance(valor, str):
        limpo = _limpar_texto_clinico(valor.strip())
        return [limpo] if limpo else []
    if not isinstance(valor, list):
        return []
    itens: list[str] = []
    for item in valor:
        texto = _limpar_texto_clinico(str(item or "").strip())
        if texto:
            itens.append(texto)
    return itens


def montar_contexto_pei(aluno: Aluno) -> dict[str, Any]:
    """Coleta e anonimiza PerfilApoio ativo, Relatorios e descricao_ia dos Trabalhos do aluno."""
    nome_aluno = aluno.nome or ""
    nome_responsavel = aluno.responsavel.nome if getattr(aluno, "responsavel", None) else ""
    nome_turma = aluno.turma.nome if getattr(aluno, "turma", None) else ""

    perfil_ativo = (
        PerfilApoio.objects.filter(
            aluno=aluno,
            ativo=True,
            deleted__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )

    necessidades: list[str] = []
    estrategias_apoio: list[str] = []
    observacoes_apoio = ""
    if perfil_ativo is not None:
        for item in perfil_ativo.necessidades or []:
            limpo = _anonimizar_texto_aluno(str(item), nome_aluno, nome_responsavel, nome_turma)
            if limpo:
                necessidades.append(limpo)
        for item in perfil_ativo.estrategias or []:
            limpo = _anonimizar_texto_aluno(str(item), nome_aluno, nome_responsavel, nome_turma)
            if limpo:
                estrategias_apoio.append(limpo)
        if perfil_ativo.observacoes:
            observacoes_apoio = _anonimizar_texto_aluno(
                perfil_ativo.observacoes,
                nome_aluno,
                nome_responsavel,
                nome_turma,
            )

    relatorios_qs = Relatorio.objects.filter(
        aluno=aluno,
        deleted__isnull=True,
    ).order_by("-created_at")[:10]

    relatorios_resumo: list[dict[str, Any]] = []
    for rel in relatorios_qs:
        dados_rel = dict(rel.dados or {})
        dados_rel.pop("disclaimer", None)
        dados_rel.pop("nome_lido", None)
        texto_json = json.dumps(dados_rel, ensure_ascii=False)
        texto_anon = _anonimizar_texto_aluno(texto_json, nome_aluno, nome_responsavel, nome_turma)
        try:
            dados_limpos = json.loads(texto_anon)
        except Exception:
            dados_limpos = {"resumo": texto_anon}
        relatorios_resumo.append(
            {
                "tipo": rel.tipo,
                "dados": dados_limpos,
            }
        )

    trabalhos_qs = (
        Trabalho.objects.filter(
            aluno=aluno,
            deleted__isnull=True,
        )
        .exclude(descricao_ia="")
        .order_by("-created_at")[:10]
    )

    descricoes_trabalhos: list[str] = []
    for trab in trabalhos_qs:
        desc_limpa = _anonimizar_texto_aluno(
            trab.descricao_ia or "",
            nome_aluno,
            nome_responsavel,
            nome_turma,
        )
        if desc_limpa:
            descricoes_trabalhos.append(desc_limpa)

    return {
        "perfil_apoio": {
            "necessidades": necessidades,
            "estrategias": estrategias_apoio,
            "observacoes": observacoes_apoio,
        },
        "relatorios": relatorios_resumo,
        "trabalhos_descricoes": descricoes_trabalhos,
    }


def gerar_rascunho_pei(
    aluno: Aluno,
    api_key: str,
    modelo: str = MODELO_PADRAO,
) -> dict[str, Any]:
    """Gera sob demanda o rascunho estruturado de PEI do aluno via Gemini (sem persistir)."""
    if not api_key:
        raise LLMError("Nenhuma credencial de IA configurada para esta escola.")

    contexto = montar_contexto_pei(aluno)
    conteudo = PROMPT_RASCUNHO_PEI + "\n\n" + json.dumps(contexto, ensure_ascii=False)

    try:
        resposta = _pedir_ao_gemini(conteudo, api_key, modelo)
        dados = _extrair_json(resposta)
    except LLMError:
        raise
    except Exception as erro:
        raise LLMError(
            "Não foi possível gerar o rascunho de PEI agora. Tente novamente em instantes."
        ) from erro

    if not isinstance(dados, dict):
        raise LLMError(
            "Não foi possível gerar o rascunho de PEI agora. Tente novamente em instantes."
        )

    objetivos = _normalizar_lista_strings(dados.get("objetivos"))
    adaptacoes = _normalizar_lista_strings(dados.get("adaptacoes"))
    estrategias = _normalizar_lista_strings(dados.get("estrategias"))
    acompanhamento = _normalizar_lista_strings(dados.get("acompanhamento"))
    observacoes = _limpar_texto_clinico(str(dados.get("observacoes") or "").strip())

    return {
        "objetivos": objetivos,
        "adaptacoes": adaptacoes,
        "estrategias": estrategias,
        "acompanhamento": acompanhamento,
        "observacoes": observacoes,
        "disclaimer": DISCLAIMER_PEI,
    }


def gerar_pdf_rascunho_pei(aluno: Aluno, rascunho: dict[str, Any]) -> bytes:
    """Gera em memória um PDF do rascunho de PEI com reportlab (sem CPF e sem responsável)."""
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=3 * cm,
    )

    estilos = getSampleStyleSheet()
    nome_turma = aluno.turma.nome if getattr(aluno, "turma", None) else ""

    conteudo = [
        Paragraph(
            "Rascunho de PEI — Plano Educacional Individualizado",
            estilos["Title"],
        ),
        Spacer(1, 0.3 * cm),
        Paragraph(f"<b>Estudante:</b> {escape(aluno.nome or '')}", estilos["Normal"]),
    ]
    if nome_turma:
        conteudo.append(Paragraph(f"<b>Turma:</b> {escape(nome_turma)}", estilos["Normal"]))
    conteudo.append(Spacer(1, 0.4 * cm))

    secoes = [
        ("Objetivos Pedagógicos", rascunho.get("objetivos") or []),
        ("Adaptações", rascunho.get("adaptacoes") or []),
        ("Estratégias", rascunho.get("estrategias") or []),
        ("Acompanhamento", rascunho.get("acompanhamento") or []),
    ]

    for titulo_secao, itens in secoes:
        conteudo.append(Paragraph(escape(titulo_secao), estilos["Heading2"]))
        if isinstance(itens, list) and itens:
            for item in itens:
                conteudo.append(Paragraph(f"• {escape(str(item))}", estilos["Normal"]))
                conteudo.append(Spacer(1, 0.1 * cm))
        else:
            conteudo.append(Paragraph("Nenhum item registrado.", estilos["Normal"]))
        conteudo.append(Spacer(1, 0.25 * cm))

    observacoes = str(rascunho.get("observacoes") or "").strip()
    if observacoes:
        conteudo.append(Paragraph("Observações", estilos["Heading2"]))
        conteudo.append(Paragraph(escape(observacoes), estilos["Normal"]))
        conteudo.append(Spacer(1, 0.3 * cm))

    disclaimer_texto = str(rascunho.get("disclaimer") or DISCLAIMER_PEI)

    def desenhar_rodape(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.grey)

        estilo_disclaimer = estilos["Normal"].clone("DisclaimerPEI")
        estilo_disclaimer.fontSize = 8
        estilo_disclaimer.leading = 10

        paragrafo = Paragraph(escape(disclaimer_texto), estilo_disclaimer)
        largura = A4[0] - 4 * cm
        altura_disclaimer = 2 * cm
        _, altura = paragrafo.wrap(largura, altura_disclaimer)
        paragrafo.drawOn(
            canvas,
            2 * cm,
            0.6 * cm + max(0, altura_disclaimer - altura),
        )

        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(
            A4[0] - 2 * cm,
            0.35 * cm,
            f"Página {doc.page}",
        )
        canvas.restoreState()

    documento.build(
        conteudo,
        onFirstPage=desenhar_rodape,
        onLaterPages=desenhar_rodape,
    )
    return buffer.getvalue()
