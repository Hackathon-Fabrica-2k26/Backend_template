import json
from io import BytesIO
from xml.sax.saxutils import escape

from django.db.models import QuerySet
from django.http import HttpResponse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.renderers import BaseRenderer

from apps.pedagogico.models import Relatorio
from apps.pedagogico.serializers import RelatorioSerializer
from apps.pedagogico.services import DISCLAIMER


class PDFRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class RelatorioViewSet(viewsets.ModelViewSet):
    """Relatórios restritos aos alunos das turmas do professor (LGPD)."""

    serializer_class = RelatorioSerializer
    filterset_fields = ["aluno", "atividade", "tipo"]
    ordering_fields = ["created_at"]

    @action(
        detail=True,
        methods=["get"],
        url_path="pdf",
        renderer_classes=[PDFRenderer],
    )
    def pdf(self, request, pk=None):
        relatorio = self.get_object()

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
        conteudo = [
            Paragraph("Relatório pedagógico", estilos["Title"]),
            Spacer(1, 0.5 * cm),
            Paragraph(
                f"Aluno: {escape(relatorio.aluno.nome)}",
                estilos["Normal"],
            ),
            Paragraph(
                f"Tipo: {escape(relatorio.tipo)}",
                estilos["Normal"],
            ),
            Spacer(1, 0.3 * cm),
        ]

        dados = relatorio.dados or {}

        for chave, valor in dados.items():
            if chave == "disclaimer":
                continue

            if isinstance(valor, (dict, list)):
                valor = json.dumps(valor, ensure_ascii=False)

            chave_formatada = escape(
                str(chave).replace("_", " ").title()
            )
            valor_formatado = escape(str(valor))

            conteudo.append(
                Paragraph(
                    f"<b>{chave_formatada}:</b> {valor_formatado}",
                    estilos["Normal"],
                )
            )
            conteudo.append(Spacer(1, 0.2 * cm))

        def desenhar_rodape(canvas, doc):
            canvas.saveState()
            canvas.setFillColor(colors.grey)

            estilo_disclaimer = estilos["Normal"].clone("Disclaimer")
            estilo_disclaimer.fontSize = 7
            estilo_disclaimer.leading = 9

            paragrafo = Paragraph(
                escape(DISCLAIMER),
                estilo_disclaimer,
            )

            largura = A4[0] - 4 * cm
            altura_disclaimer = 2 * cm
            _, altura = paragrafo.wrap(largura, altura_disclaimer)

            paragrafo.drawOn(
                canvas,
                2 * cm,
                0.5 * cm + max(0, altura_disclaimer - altura),
            )

            canvas.setFont("Helvetica", 8)
            canvas.drawRightString(
                A4[0] - 2 * cm,
                0.3 * cm,
                f"Página {doc.page}",
            )
            canvas.restoreState()

        documento.build(
            conteudo,
            onFirstPage=desenhar_rodape,
            onLaterPages=desenhar_rodape,
        )

        resposta = HttpResponse(
            buffer.getvalue(),
            content_type="application/pdf",
        )
        resposta["Content-Disposition"] = (
            f'attachment; filename="relatorio-{relatorio.pk}.pdf"'
        )
        return resposta

    def get_queryset(self) -> QuerySet[Relatorio]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Relatorio.objects.none()

        return Relatorio.objects.filter(
            aluno__turma__professores=self.request.user
        ).distinct()