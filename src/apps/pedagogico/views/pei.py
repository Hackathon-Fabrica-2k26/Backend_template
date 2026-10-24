"""Endpoints sob demanda de rascunho de PEI e PDF do aluno (B#46)."""

from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alunos.models import Aluno
from apps.escolas.services.escola_usuario import config_ia_do_usuario
from apps.pedagogico.services.llm import MODELO_PADRAO, LLMError
from apps.pedagogico.services.pei import gerar_pdf_rascunho_pei, gerar_rascunho_pei
from apps.pedagogico.views.relatorio import PDFRenderer


class RascunhoPEIRespostaSerializer(serializers.Serializer):
    objetivos = serializers.ListField(child=serializers.CharField())
    adaptacoes = serializers.ListField(child=serializers.CharField())
    estrategias = serializers.ListField(child=serializers.CharField())
    acompanhamento = serializers.ListField(child=serializers.CharField())
    observacoes = serializers.CharField(allow_blank=True)
    disclaimer = serializers.CharField()


def _obter_aluno_do_professor(request, aluno_id: int) -> Aluno | None:
    return (
        Aluno.objects.filter(
            pk=aluno_id,
            turma__professores=request.user,
            deleted__isnull=True,
        )
        .select_related("turma", "turma__escola", "responsavel")
        .first()
    )


class AlunoRascunhoPEIView(APIView):
    """Gera sob demanda o rascunho de PEI de um aluno das turmas do professor."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = RascunhoPEIRespostaSerializer

    @extend_schema(
        summary="Gerar rascunho de PEI do aluno sob demanda",
        description=(
            "Consolida sob demanda o PerfilApoio ativo, os Relatorios e as "
            "descrições de Trabalhos do aluno (anonimizados) e solicita ao Gemini "
            "um rascunho estruturado de PEI em linguagem estritamente pedagógica "
            "(sem diagnóstico clínico e sem persistir dados)."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID do aluno.",
            ),
        ],
        request=None,
        responses={
            200: RascunhoPEIRespostaSerializer,
            404: OpenApiResponse(
                description="Aluno não encontrado ou não pertence às turmas do professor."
            ),
            502: OpenApiResponse(description="Falha ao comunicar com o provedor de IA."),
        },
    )
    def post(self, request, id: int) -> Response:
        aluno = _obter_aluno_do_professor(request, id)
        if aluno is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        escola = getattr(request.user, "escola", None) or (
            aluno.turma.escola if aluno.turma else None
        )
        config = config_ia_do_usuario(request.user, escola=escola)

        try:
            rascunho = gerar_rascunho_pei(
                aluno=aluno,
                api_key=config.api_key if config else "",
                modelo=config.modelo if config and config.modelo else MODELO_PADRAO,
            )
        except LLMError as erro:
            return Response(
                {"erro": str(erro)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(rascunho, status=status.HTTP_200_OK)


class AlunoRascunhoPEIPDFView(APIView):
    """Exporta sob demanda o PDF do rascunho de PEI do aluno (sem CPF e sem responsável)."""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Baixar PDF do rascunho de PEI do aluno sob demanda",
        description=(
            "Gera o rascunho de PEI sob demanda e retorna o documento em formato PDF "
            "com aviso ético de revisão da professora e da coordenação, sem CPF e sem "
            "dados do responsável."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID do aluno.",
            ),
        ],
        responses={
            (200, "application/pdf"): OpenApiResponse(
                response=OpenApiTypes.BINARY,
                description="PDF do rascunho de PEI gerado sob demanda.",
            ),
            404: OpenApiResponse(
                description="Aluno não encontrado ou não pertence às turmas do professor."
            ),
            502: OpenApiResponse(description="Falha ao comunicar com o provedor de IA."),
        },
    )
    def get(self, request, id: int):
        aluno = _obter_aluno_do_professor(request, id)
        if aluno is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        escola = getattr(request.user, "escola", None) or (
            aluno.turma.escola if aluno.turma else None
        )
        config = config_ia_do_usuario(request.user, escola=escola)

        try:
            rascunho = gerar_rascunho_pei(
                aluno=aluno,
                api_key=config.api_key if config else "",
                modelo=config.modelo if config and config.modelo else MODELO_PADRAO,
            )
        except LLMError as erro:
            return Response(
                {"erro": str(erro)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        pdf_bytes = gerar_pdf_rascunho_pei(aluno=aluno, rascunho=rascunho)
        resposta = HttpResponse(pdf_bytes, content_type=PDFRenderer.media_type)
        resposta["Content-Disposition"] = (
            f'attachment; filename="rascunho-pei-aluno-{aluno.pk}.pdf"'
        )
        return resposta
