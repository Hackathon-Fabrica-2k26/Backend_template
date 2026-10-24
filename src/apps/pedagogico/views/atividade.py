from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from apps.pedagogico.models import Atividade
from apps.pedagogico.serializers import (
    AtividadeSerializer,
    EnvioTrabalhosSerializer,
    EnvioTrabalhosUploadSerializer,
)
from apps.pedagogico.services import LLMError, processar_envio_trabalhos


@extend_schema_view(
    list=extend_schema(
        summary="Listar atividades",
        description="Retorna as atividades das turmas do professor autenticado.",
        parameters=[
            OpenApiParameter(
                name="turma",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Filtra atividades pelo ID da turma.",
            ),
            OpenApiParameter(
                name="search",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Busca textual por título ou objetivo da atividade.",
            ),
            OpenApiParameter(
                name="ordering",
                type=str,
                location=OpenApiParameter.QUERY,
                description="Ordena por `titulo`, `-titulo`, `created_at` ou `-created_at`.",
            ),
        ],
    ),
    create=extend_schema(summary="Criar atividade"),
    retrieve=extend_schema(summary="Detalhar atividade"),
    update=extend_schema(summary="Atualizar atividade"),
    partial_update=extend_schema(summary="Atualizar atividade parcialmente"),
    destroy=extend_schema(summary="Remover atividade"),
)
class AtividadeViewSet(viewsets.ModelViewSet):
    serializer_class = AtividadeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["titulo", "objetivo"]
    ordering_fields = ["titulo", "created_at"]
    ordering = ["-created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Atividade.objects.none()
        qs = (
            Atividade.objects.filter(turma__professores=self.request.user)
            .select_related("turma", "criada_por")
            .distinct()
        )
        turma_id = self.request.query_params.get("turma")
        if turma_id and turma_id.isdigit():
            qs = qs.filter(turma_id=int(turma_id))
        return qs

    def perform_create(self, serializer):
        serializer.save(criada_por=self.request.user)

    @extend_schema(
        summary="Enviar trabalhos de alunos por foto/arquivo",
        description=(
            "Recebe múltiplos arquivos (PDF, PNG, JPG, WEBP ou DOCX até 20 MB cada), "
            "analisa em memória via Gemini (extraindo nome, descrição e análise pedagógica), "
            "casa automaticamente com os alunos da turma, gera relatórios do tipo 'atividade' "
            "para os trabalhos confirmados e descarta os arquivos originais imediatamente (LGPD)."
        ),
        request=EnvioTrabalhosUploadSerializer,
        responses={
            201: EnvioTrabalhosSerializer,
            400: OpenApiResponse(
                description="Arquivos inválidos ou formato/tamanho não suportado."
            ),
            404: OpenApiResponse(description="Atividade não encontrada."),
            502: OpenApiResponse(description="Falha ao comunicar com o provedor de IA."),
        },
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="trabalhos",
        parser_classes=[MultiPartParser, FormParser],
    )
    def trabalhos(self, request: Request, pk=None) -> Response:
        atividade = self.get_object()
        arquivos = request.FILES.getlist("arquivos")
        if not arquivos:
            return Response(
                {"arquivos": ["Envie ao menos um arquivo no campo 'arquivos'."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            envio = processar_envio_trabalhos(
                atividade=atividade,
                arquivos=arquivos,
                usuario=request.user,
            )
        except ValueError as exc:
            return Response(
                {"arquivos": [str(exc)]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except LLMError as exc:
            return Response(
                {"erro": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        serializer = EnvioTrabalhosSerializer(envio)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
