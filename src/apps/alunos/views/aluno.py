import json
from io import BytesIO
from xml.sax.saxutils import escape

from django.db.models import Count, Q, QuerySet
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.alunos.models import Aluno
from apps.alunos.serializers import AlunoSerializer
from apps.pedagogico.models import Relatorio
from apps.pedagogico.services import DISCLAIMER


class AlunoViewSet(viewsets.ModelViewSet):
    serializer_class = AlunoSerializer
    filterset_fields = ["turma", "ativo"]
    search_fields = ["nome", "matricula"]
    ordering_fields = ["nome", "created_at"]

    @action(detail=True, methods=["get"], url_path="relatorios")
    def relatorios(self, request, pk=None):
        aluno = get_object_or_404(self.get_queryset(), pk=pk)

        relatorios = Relatorio.objects.filter(aluno=aluno)

        tipo = request.query_params.get("tipo")
        atividade_id = request.query_params.get("atividade")

        if tipo:
            relatorios = relatorios.filter(tipo=tipo)

        if atividade_id:
            relatorios = relatorios.filter(atividade_id=atividade_id)

        relatorios = relatorios.distinct().order_by("-created_at")

        dados = [
            {
                "id": relatorio.pk,
                "aluno": relatorio.aluno_id,
                "atividade": relatorio.atividade_id,
                "tipo": relatorio.tipo,
                "dados": relatorio.dados,
                "created_at": relatorio.created_at,
                "updated_at": relatorio.updated_at,
                "disclaimer": relatorio.disclaimer or DISCLAIMER,
            }
            for relatorio in relatorios
        ]

        page = self.paginate_queryset(dados)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(dados)

    @action(detail=True, methods=["get"], url_path="relatorios/pdf")
    def relatorios_pdf(self, request, pk=None):
        aluno = get_object_or_404(self.get_queryset(), pk=pk)

        relatorios = Relatorio.objects.filter(aluno=aluno).order_by("-created_at")

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
            Paragraph("Relatórios pedagógicos", estilos["Title"]),
            Paragraph(
                f"Aluno: {escape(aluno.nome)}",
                estilos["Heading2"],
            ),
            Spacer(1, 0.5 * cm),
        ]

        for indice, relatorio in enumerate(relatorios):
            if indice > 0:
                conteudo.append(PageBreak())

            conteudo.append(
                Paragraph(
                    f"Relatório #{relatorio.pk}",
                    estilos["Heading2"],
                )
            )
            conteudo.append(
                Paragraph(
                    f"Tipo: {escape(relatorio.tipo)}",
                    estilos["Normal"],
                )
            )
            conteudo.append(Spacer(1, 0.2 * cm))

            dados_relatorio = relatorio.dados or {}

            for chave, valor in dados_relatorio.items():
                if chave == "disclaimer":
                    continue

                if isinstance(valor, (dict, list)):
                    valor = json.dumps(valor, ensure_ascii=False)

                chave_formatada = escape(str(chave).replace("_", " ").title())
                valor_formatado = escape(str(valor))

                conteudo.append(
                    Paragraph(
                        f"<b>{chave_formatada}:</b> {valor_formatado}",
                        estilos["Normal"],
                    )
                )
                conteudo.append(Spacer(1, 0.2 * cm))

            conteudo.append(Spacer(1, 0.4 * cm))

        estilo_disclaimer = ParagraphStyle(
            "Disclaimer",
            parent=estilos["Normal"],
            fontSize=7,
            leading=9,
            textColor=colors.grey,
        )

        def desenhar_rodape(canvas, doc):
            canvas.saveState()

            paragrafo = Paragraph(
                escape(DISCLAIMER),
                estilo_disclaimer,
            )
            largura = A4[0] - 4 * cm
            _, altura = paragrafo.wrap(largura, 2 * cm)
            paragrafo.drawOn(
                canvas,
                2 * cm,
                max(0.3 * cm, 0.5 * cm + 2 * cm - altura),
            )

            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(colors.grey)
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
        resposta["Content-Disposition"] = f'attachment; filename="relatorios-aluno-{aluno.pk}.pdf"'
        return resposta

    def get_queryset(self) -> QuerySet[Aluno]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Aluno.objects.none()

        return (
            Aluno.objects.filter(turma__professores=self.request.user)
            .annotate(
                total_relatorios=Count(
                    "relatorios",
                    filter=Q(relatorios__deleted__isnull=True),
                    distinct=True,
                ),
                total_trabalhos=Count(
                    "trabalhos",
                    filter=Q(trabalhos__deleted__isnull=True),
                    distinct=True,
                ),
            )
            .distinct()
        )
