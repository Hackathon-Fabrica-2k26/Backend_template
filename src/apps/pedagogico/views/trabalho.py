from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from apps.pedagogico.models import Trabalho
from apps.pedagogico.serializers import TrabalhoConfirmacaoSerializer, TrabalhoSerializer
from apps.pedagogico.services import confirmar_trabalho


@extend_schema_view(
    list=extend_schema(
        summary="Listar trabalhos analisados",
        description=(
            "Retorna os trabalhos analisados das atividades das turmas do professor autenticado. "
            "Fotos originais não são armazenadas (LGPD)."
        ),
        parameters=[
            OpenApiParameter(
                name="atividade",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Filtra trabalhos pelo ID da atividade.",
            ),
            OpenApiParameter(
                name="aluno",
                type=int,
                location=OpenApiParameter.QUERY,
                description="Filtra trabalhos pelo ID do aluno.",
            ),
            OpenApiParameter(
                name="status",
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    "Filtra pelo status da análise (`recebido`, `analisando`, `analisado`, `erro`)."
                ),
            ),
            OpenApiParameter(
                name="identificacao",
                type=str,
                location=OpenApiParameter.QUERY,
                description=(
                    "Filtra pelo status de identificação "
                    "(`pendente`, `automatica`, `confirmada`, `sem_aluno`, `sem_consentimento`)."
                ),
            ),
        ],
    ),
    retrieve=extend_schema(summary="Detalhar trabalho analisado"),
    partial_update=extend_schema(
        summary="Confirmar ou atribuir aluno a um trabalho",
        description=(
            "Permite ao professor confirmar ou atribuir manualmente o aluno de um trabalho "
            "e gera o Relatorio do tipo 'atividade' correspondente."
        ),
        request=TrabalhoConfirmacaoSerializer,
        responses={
            200: TrabalhoSerializer,
            400: OpenApiResponse(description="Dados inválidos ou aluno fora da turma."),
            404: OpenApiResponse(description="Trabalho não encontrado."),
        },
    ),
)
class TrabalhoViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = TrabalhoSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Trabalho.objects.none()
        qs = (
            Trabalho.objects.filter(atividade__turma__professores=self.request.user)
            .select_related("atividade", "atividade__turma", "aluno", "variacao", "envio")
            .distinct()
        )
        atividade_id = self.request.query_params.get("atividade")
        if atividade_id and atividade_id.isdigit():
            qs = qs.filter(atividade_id=int(atividade_id))
        aluno_id = self.request.query_params.get("aluno")
        if aluno_id and aluno_id.isdigit():
            qs = qs.filter(aluno_id=int(aluno_id))
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        ident_param = self.request.query_params.get("identificacao")
        if ident_param:
            qs = qs.filter(identificacao=ident_param)
        return qs

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        trabalho = self.get_object()
        serializer = TrabalhoConfirmacaoSerializer(
            data=request.data,
            context={"trabalho": trabalho, "request": request},
        )
        serializer.is_valid(raise_exception=True)

        trabalho_atualizado = confirmar_trabalho(
            trabalho=trabalho,
            aluno=serializer.validated_data["aluno"],
            usuario=request.user,
        )
        return Response(
            TrabalhoSerializer(trabalho_atualizado).data,
            status=status.HTTP_200_OK,
        )
