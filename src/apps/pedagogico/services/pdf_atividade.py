"""Serviço de geração e estilização profissional de atividades pedagógicas em PDF via ReportLab.

Diretrizes e Regras:
- Layout educacional limpo, atraente e adequado para crianças dos anos iniciais (1º ano EF).
- Cabeçalho escolar com campos de preenchimento (Estudante, Data, Turma).
- Identificação neutra da versão da atividade (ex.: prova_v1, prova_v2) para evitar estigmatização (Inclusão).
- LGPD: NUNCA inclui nomes de alunos em variações, diagnósticos, laudos, CIDs ou menções clínicas.
- Identificação automática de questões, alternativas, áreas de desenho e linhas pautadas para resposta.
- Numeração dinâmica de páginas (Página X de Y) via NumberedCanvas.
"""

from io import BytesIO
import os
import re
from typing import Any
from xml.sax.saxutils import escape

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

# Paleta Marsupi institucional e educacional
VERDE_MARSUPI_ESCURO = colors.HexColor("#1A3628")
VERDE_MARSUPI = colors.HexColor("#274D3D")
VERDE_MARSUPI_CLARO = colors.HexColor("#3B7A57")
VERDE_FUNDO_SUAVE = colors.HexColor("#F2F7F4")
CINZA_TEXTO = colors.HexColor("#2D3748")
CINZA_SUAVE = colors.HexColor("#718096")
CINZA_BORDA = colors.HexColor("#CBD5E0")
CINZA_LINHA = colors.HexColor("#A0AEC0")
BRANCO = colors.HexColor("#FFFFFF")


class NumberedCanvas(canvas.Canvas):
    """Canvas com duas passagens para calcular o total real de páginas e desenhar rodapé."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict[str, Any]] = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, total_pages: int):
        self.saveState()
        largura, altura = A4

        # Linha decorativa no rodapé
        self.setStrokeColor(CINZA_BORDA)
        self.setLineWidth(0.6)
        self.line(1.5 * cm, 1.4 * cm, largura - 1.5 * cm, 1.4 * cm)

        # Informações de rodapé
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(VERDE_MARSUPI)
        self.drawString(1.5 * cm, 0.9 * cm, "Marsupi")

        self.setFont("Helvetica", 8)
        self.setFillColor(CINZA_SUAVE)
        self.drawString(2.8 * cm, 0.9 * cm, "• Plataforma de Apoio Pedagógico Inclusivo")

        texto_paginacao = f"Página {self._pageNumber} de {total_pages}"
        self.drawRightString(largura - 1.5 * cm, 0.9 * cm, texto_paginacao)

        self.restoreState()


def _obter_caminho_logo() -> str | None:
    """Busca o arquivo de logotipo estático se existir no projeto."""
    possiveis_caminhos = [
        os.path.join(settings.BASE_DIR, "apps", "users", "assets", "logo-email.png"),
        os.path.join(settings.BASE_DIR, "src", "apps", "users", "assets", "logo-email.png"),
    ]
    for caminho in possiveis_caminhos:
        if os.path.exists(caminho):
            return caminho
    return None


def _construir_estilos() -> dict[str, ParagraphStyle]:
    """Cria estilos tipográficos com espaçamento e legibilidade infantil adequada."""
    base = getSampleStyleSheet()

    return {
        "Titulo": ParagraphStyle(
            "MarsupiTitulo",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=VERDE_MARSUPI_ESCURO,
            alignment=0,
            spaceAfter=4,
        ),
        "Subtitulo": ParagraphStyle(
            "MarsupiSubtitulo",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=15,
            textColor=VERDE_MARSUPI,
            spaceAfter=3,
        ),
        "ObjetivoTexto": ParagraphStyle(
            "MarsupiObjetivo",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=VERDE_MARSUPI_ESCURO,
        ),
        "CabecalhoTexto": ParagraphStyle(
            "MarsupiCabecalho",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            textColor=CINZA_TEXTO,
        ),
        "CabecalhoDestaque": ParagraphStyle(
            "MarsupiCabecalhoDestaque",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=14,
            textColor=VERDE_MARSUPI_ESCURO,
        ),
        "Badge": ParagraphStyle(
            "MarsupiBadge",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=VERDE_MARSUPI_ESCURO,
            alignment=1,
        ),
        "Questao": ParagraphStyle(
            "MarsupiQuestao",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=15,
            textColor=VERDE_MARSUPI_ESCURO,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "TextoNormal": ParagraphStyle(
            "MarsupiNormal",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=15,
            textColor=CINZA_TEXTO,
            spaceAfter=4,
        ),
        "Alternativa": ParagraphStyle(
            "MarsupiAlternativa",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=CINZA_TEXTO,
            leftIndent=15,
            spaceAfter=3,
        ),
        "Legenda": ParagraphStyle(
            "MarsupiLegenda",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=8,
            leading=10,
            textColor=CINZA_SUAVE,
            alignment=2,
        ),
    }


def _criar_cabecalho_escolar(
    escola_nome: str,
    turma_nome: str,
    rotulo_versao: str,
    estilos: dict[str, ParagraphStyle],
) -> Table:
    """Monta o cabeçalho padronizado da atividade com campos de preenchimento para o aluno."""
    largura_total = 18.0 * cm
    caminho_logo = _obter_caminho_logo()

    # Coluna 1: Informações da Escola e Aluno (largura 13.5 cm)
    nome_escola_exibicao = escola_nome or "Escola de Ensino Fundamental"
    turma_exibicao = f"Turma: {turma_nome}" if turma_nome else "Turma: __________________"

    texto_escola = Paragraph(f"<b>{escape(nome_escola_exibicao)}</b>", estilos["CabecalhoDestaque"])
    texto_linha_aluno = Paragraph(
        "<b>Estudante:</b> ____________________________________________________________________",
        estilos["CabecalhoTexto"],
    )
    texto_linha_meta = Paragraph(
        f"<b>Data:</b> _____/_____/_________ &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; <b>{escape(turma_exibicao)}</b>",
        estilos["CabecalhoTexto"],
    )

    bloco_esquerdo = [
        texto_escola,
        Spacer(1, 0.15 * cm),
        texto_linha_aluno,
        Spacer(1, 0.12 * cm),
        texto_linha_meta,
    ]

    # Coluna 2: Logo / Selo + Badge neutro de versão (largura 4.5 cm)
    bloco_direito = []
    if caminho_logo:
        try:
            # Imagem proporcional de aprox 2.8 cm de largura por 1.1 cm de altura
            img_logo = Image(caminho_logo, width=2.8 * cm, height=1.12 * cm)
            bloco_direito.append(img_logo)
            bloco_direito.append(Spacer(1, 0.1 * cm))
        except Exception:
            pass

    # Rótulo neutro (sempre seguro contra estigmas)
    rotulo_limpo = rotulo_versao.strip() if rotulo_versao else "Versão Geral"
    badge_tabela = Table(
        [[Paragraph(f"Cód: {escape(rotulo_limpo)}", estilos["Badge"])]],
        colWidths=[4.2 * cm],
    )
    badge_tabela.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), VERDE_FUNDO_SUAVE),
                ("BOX", (0, 0), (-1, -1), 0.8, VERDE_MARSUPI),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    bloco_direito.append(badge_tabela)

    tabela_cabecalho = Table(
        [[bloco_esquerdo, bloco_direito]],
        colWidths=[13.5 * cm, 4.5 * cm],
    )
    tabela_cabecalho.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (-1, -1), 1, VERDE_MARSUPI),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFDFB")),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    return tabela_cabecalho


def _criar_linhas_resposta(linhas: int = 2) -> Table:
    """Gera linhas pautadas discretas para a criança escrever com lápis."""
    dados = [[""] for _ in range(linhas)]
    tabela_linhas = Table(dados, colWidths=[18.0 * cm], rowHeights=[0.75 * cm] * linhas)
    tabela_linhas.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, -1), 0.75, CINZA_LINHA),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return tabela_linhas


def _criar_caixa_desenho(altura_cm: float = 4.2) -> Table:
    """Gera uma área delimitada para desenho ou colagem da criança."""
    estilos = _construir_estilos()
    conteudo = [
        Paragraph("Espaço para desenho / colagem", estilos["Legenda"]),
    ]
    tabela_caixa = Table([[conteudo]], colWidths=[18.0 * cm], rowHeights=[altura_cm * cm])
    tabela_caixa.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.8, CINZA_BORDA),
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFCFA")),
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return tabela_caixa


PADRAO_QUESTAO = re.compile(
    r"^(?:Quest[aã]o\s*)?(\d+)[.)\-\s](.*)$",
    re.IGNORECASE,
)
PADRAO_ALTERNATIVA = re.compile(
    r"^([a-eA-E][.)\-]|\([a-eA-E\s]*\)|\b[a-eA-E]\))\s*(.*)$"
)
PADRAO_DESENHO = re.compile(
    r"\b(desenhe|fa[çc]a um desenho|ilustre|pinte|cole|represente com desenho)\b",
    re.IGNORECASE,
)
PADRAO_ESCRITA = re.compile(
    r"\b(escreva|complete|copie|responda|qual|quais|quanto|quantos|calcule|resolva)\b",
    re.IGNORECASE,
)


def _processar_conteudo_atividade(
    conteudo_bruto: str,
    estilos: dict[str, ParagraphStyle],
) -> list[Any]:
    """Interpreta e diagramada o conteúdo da atividade em elementos visuais do ReportLab."""
    elementos: list[Any] = []
    linhas = [linha.strip() for linha in (conteudo_bruto or "").split("\n") if linha.strip()]

    i = 0
    while i < len(linhas):
        linha = linhas[i]

        # 1. Verifica se é uma Questão numerada
        match_questao = PADRAO_QUESTAO.match(linha)
        if match_questao:
            numero = match_questao.group(1)
            enunciado = match_questao.group(2).strip()
            texto_formatado = f"<b>{numero}.</b> {escape(enunciado)}" if enunciado else f"<b>{numero}.</b>"

            bloco_questao: list[Any] = [
                Paragraph(texto_formatado, estilos["Questao"]),
            ]

            # Analisa se a questão solicita desenho ou escrita
            if PADRAO_DESENHO.search(linha):
                bloco_questao.append(Spacer(1, 0.2 * cm))
                bloco_questao.append(_criar_caixa_desenho(altura_cm=4.0))
                bloco_questao.append(Spacer(1, 0.3 * cm))
            elif PADRAO_ESCRITA.search(linha):
                # Olha se a próxima linha é alternativa antes de pôr linhas pautadas
                proxima_e_alternativa = (
                    i + 1 < len(linhas) and PADRAO_ALTERNATIVA.match(linhas[i + 1])
                )
                if not proxima_e_alternativa:
                    bloco_questao.append(Spacer(1, 0.2 * cm))
                    bloco_questao.append(_criar_linhas_resposta(linhas=2))
                    bloco_questao.append(Spacer(1, 0.3 * cm))

            elementos.append(KeepTogether(bloco_questao))
            i += 1
            continue

        # 2. Verifica se é uma alternativa (A, B, C...)
        match_alt = PADRAO_ALTERNATIVA.match(linha)
        if match_alt:
            rotulo_alt = match_alt.group(1).strip()
            texto_alt = match_alt.group(2).strip()
            # Formata com quadradinho ou parênteses para marcar
            if not rotulo_alt.startswith("(") and not rotulo_alt.startswith("["):
                letra = rotulo_alt.replace(".", "").replace(")", "").replace("-", "").strip()
                texto_formatado = f"( &nbsp; ) &nbsp;<b>{escape(letra)})</b> {escape(texto_alt)}"
            else:
                texto_formatado = f"{escape(rotulo_alt)} {escape(texto_alt)}"

            elementos.append(Paragraph(texto_formatado, estilos["Alternativa"]))
            i += 1
            continue

        # 3. Texto normal / instruções gerais
        elementos.append(Paragraph(escape(linha), estilos["TextoNormal"]))
        i += 1

    return elementos


def gerar_pdf_variacao(variacao: Any) -> bytes:
    """Gera o PDF estilizado e pronto para impressão de uma variação individual de atividade.

    Segurança e LGPD:
    - Rótulo neutro da variação (ex.: prova_v1).
    - Não expõe nome de alunos atribuídos nem termos clínicos/diagnósticos.
    """
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2.0 * cm,
        pageCompression=0,
    )

    estilos = _construir_estilos()
    atividade = variacao.atividade
    turma = getattr(atividade, "turma", None)
    escola = getattr(turma, "escola", None)

    escola_nome = getattr(escola, "nome", "") if escola else ""
    turma_nome = getattr(turma, "nome", "") if turma else ""

    conteudo_fluxo: list[Any] = []

    # 1. Cabeçalho Escolar
    conteudo_fluxo.append(
        _criar_cabecalho_escolar(
            escola_nome=escola_nome,
            turma_nome=turma_nome,
            rotulo_versao=variacao.rotulo or f"prova_v{variacao.numero}",
            estilos=estilos,
        )
    )
    conteudo_fluxo.append(Spacer(1, 0.45 * cm))

    # 2. Título da Atividade
    conteudo_fluxo.append(Paragraph(escape(atividade.titulo), estilos["Titulo"]))
    conteudo_fluxo.append(
        HRFlowable(
            width="100%",
            thickness=1.2,
            color=VERDE_MARSUPI_CLARO,
            spaceBefore=2,
            spaceAfter=8,
        )
    )

    # 3. Objetivo pedagógico (se houver)
    if atividade.objetivo and atividade.objetivo.strip():
        caixa_objetivo = Table(
            [[Paragraph(f"<b>Objetivo:</b> {escape(atividade.objetivo.strip())}", estilos["ObjetivoTexto"])]],
            colWidths=[18.0 * cm],
        )
        caixa_objetivo.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), VERDE_FUNDO_SUAVE),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, VERDE_MARSUPI),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        conteudo_fluxo.append(caixa_objetivo)
        conteudo_fluxo.append(Spacer(1, 0.4 * cm))

    # 4. Conteúdo estruturado da variação
    elementos_conteudo = _processar_conteudo_atividade(variacao.conteudo, estilos)
    conteudo_fluxo.extend(elementos_conteudo)

    documento.build(conteudo_fluxo, canvasmaker=NumberedCanvas)
    return buffer.getvalue()


def gerar_pdf_atividade_completa(
    atividade: Any,
    incluir_todas_variacoes: bool = False,
) -> bytes:
    """Gera PDF da atividade.

    Se `incluir_todas_variacoes=True`, encadeia todas as variações aprovadas/ativas
    com PageBreak para que a professora possa imprimir todas as versões da turma em lote.
    Caso contrário, gera a versão geral (ou a primeira variação, ou o texto original).
    """
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2.0 * cm,
        pageCompression=0,
    )

    estilos = _construir_estilos()
    turma = getattr(atividade, "turma", None)
    escola = getattr(turma, "escola", None)
    escola_nome = getattr(escola, "nome", "") if escola else ""
    turma_nome = getattr(turma, "nome", "") if turma else ""

    variacoes = list(
        atividade.variacoes.exclude(status="descartada").order_by("numero")
    )

    conteudo_fluxo: list[Any] = []

    if incluir_todas_variacoes and variacoes:
        for idx, var in enumerate(variacoes):
            if idx > 0:
                conteudo_fluxo.append(PageBreak())

            # Cabeçalho da variação
            conteudo_fluxo.append(
                _criar_cabecalho_escolar(
                    escola_nome=escola_nome,
                    turma_nome=turma_nome,
                    rotulo_versao=var.rotulo or f"prova_v{var.numero}",
                    estilos=estilos,
                )
            )
            conteudo_fluxo.append(Spacer(1, 0.45 * cm))
            conteudo_fluxo.append(Paragraph(escape(atividade.titulo), estilos["Titulo"]))
            conteudo_fluxo.append(
                HRFlowable(
                    width="100%",
                    thickness=1.2,
                    color=VERDE_MARSUPI_CLARO,
                    spaceBefore=2,
                    spaceAfter=8,
                )
            )

            elementos_var = _processar_conteudo_atividade(var.conteudo, estilos)
            conteudo_fluxo.extend(elementos_var)
    else:
        # Versão geral ou primeira variação ou texto original
        var_geral = next((v for v in variacoes if v.eh_geral), None) or (
            variacoes[0] if variacoes else None
        )
        rotulo = var_geral.rotulo if var_geral else "Versão Geral"
        texto = var_geral.conteudo if var_geral else (atividade.texto_original or "")

        conteudo_fluxo.append(
            _criar_cabecalho_escolar(
                escola_nome=escola_nome,
                turma_nome=turma_nome,
                rotulo_versao=rotulo,
                estilos=estilos,
            )
        )
        conteudo_fluxo.append(Spacer(1, 0.45 * cm))
        conteudo_fluxo.append(Paragraph(escape(atividade.titulo), estilos["Titulo"]))
        conteudo_fluxo.append(
            HRFlowable(
                width="100%",
                thickness=1.2,
                color=VERDE_MARSUPI_CLARO,
                spaceBefore=2,
                spaceAfter=8,
            )
        )

        if atividade.objetivo and atividade.objetivo.strip():
            caixa_objetivo = Table(
                [[Paragraph(f"<b>Objetivo:</b> {escape(atividade.objetivo.strip())}", estilos["ObjetivoTexto"])]],
                colWidths=[18.0 * cm],
            )
            caixa_objetivo.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, -1), VERDE_FUNDO_SUAVE),
                        ("LINEBEFORE", (0, 0), (0, -1), 3, VERDE_MARSUPI),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                        ("LEFTPADDING", (0, 0), (-1, -1), 8),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            conteudo_fluxo.append(caixa_objetivo)
            conteudo_fluxo.append(Spacer(1, 0.4 * cm))

        elementos = _processar_conteudo_atividade(texto, estilos)
        conteudo_fluxo.extend(elementos)

    documento.build(conteudo_fluxo, canvasmaker=NumberedCanvas)
    return buffer.getvalue()
