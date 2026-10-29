from io import BytesIO
from xml.sax.saxutils import escape

from django.db.models import QuerySet
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.renderers import BaseRenderer
from rest_framework.response import Response

from apps.pedagogico.models import Atividade, AtividadeVariacao
from apps.pedagogico.serializers import AtividadeVariacaoSerializer
from apps.pedagogico.services.pdf_atividade import gerar_pdf_variacao


class PDFRenderer(BaseRenderer):
    media_type = "application/pdf"
    format = "pdf"
    charset = None

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class AtividadeVariacaoViewSet(viewsets.ModelViewSet):
    """Variações restritas às atividades das turmas do professor (LGPD)."""

    serializer_class = AtividadeVariacaoSerializer
    filterset_fields = ["atividade", "status", "eh_geral"]
    search_fields = ["rotulo", "conteudo"]
    ordering_fields = ["numero", "created_at"]

    def get_queryset(self) -> QuerySet[AtividadeVariacao]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return AtividadeVariacao.objects.none()
        return AtividadeVariacao.objects.filter(
            atividade__turma__professores=self.request.user
        ).distinct()

    @extend_schema(
        request=None,
        responses={200: AtividadeVariacaoSerializer},
    )
    @action(detail=True, methods=["post"], url_path="aprovar")
    def aprovar(self, request, pk=None):
        variacao = self.get_object()
        variacao.status = AtividadeVariacao.StatusChoices.APROVADA
        variacao.aprovada_por = request.user
        variacao.aprovada_em = timezone.now()
        variacao.save(update_fields=["status", "aprovada_por", "aprovada_em", "updated_at"])

        atividade = variacao.atividade
        variacoes_ativas = atividade.variacoes.exclude(
            status=AtividadeVariacao.StatusChoices.DESCARTADA
        )
        if variacoes_ativas.exists() and not variacoes_ativas.exclude(
            status=AtividadeVariacao.StatusChoices.APROVADA
        ).exists():
            atividade.status = Atividade.StatusChoices.APROVADA
            atividade.save(update_fields=["status", "updated_at"])

        serializer = self.get_serializer(variacao)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        responses={(200, "application/pdf"): OpenApiTypes.BINARY},
    )
    @action(
        detail=True,
        methods=["get"],
        url_path="pdf",
        renderer_classes=[PDFRenderer],
    )
    def pdf(self, request, pk=None):
        """Gera PDF para impressão contendo apenas o rótulo neutro (prova_vN),
        o título da atividade e o conteúdo (NUNCA nome de aluno ou condição).
        """
        variacao = self.get_object()
        pdf_bytes = gerar_pdf_variacao(variacao)

        resposta = HttpResponse(
            pdf_bytes,
            content_type="application/pdf",
        )
        resposta["Content-Disposition"] = (
            f'attachment; filename="{variacao.rotulo}-atividade-{variacao.atividade_id}.pdf"'
        )
        return resposta
