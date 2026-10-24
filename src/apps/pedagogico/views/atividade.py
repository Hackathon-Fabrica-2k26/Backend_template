from django.db.models import Q, QuerySet
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response

from apps.pedagogico.models import Atividade
from apps.pedagogico.serializers import (
    AtividadeSerializer,
    EnvioTrabalhosSerializer,
    TrabalhoUploadSerializer,
)
from apps.pedagogico.services import (
    LLMError,
    processar_envio_trabalhos,
    professor_tem_acesso,
)


class AtividadeViewSet(viewsets.ModelViewSet):
    """Atividades restritas aos alunos das turmas do professor (LGPD)."""

    serializer_class = AtividadeSerializer
    filterset_fields = ["aluno"]
    search_fields = ["nome"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self) -> QuerySet[Atividade]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Atividade.objects.none()

        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Atividade.objects.all()

        filtro = Q(aluno__turma__professores=user)
        if any(f.name == "turma" for f in Atividade._meta.fields):
            filtro |= Q(turma__professores=user)

        return Atividade.objects.filter(filtro).distinct()

    @extend_schema(
        request=TrabalhoUploadSerializer,
        responses={
            201: EnvioTrabalhosSerializer,
            400: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
    )
    @action(
        detail=True,
        methods=["post"],
        parser_classes=[MultiPartParser, FormParser],
        url_path="trabalhos",
    )
    def trabalhos(self, request, pk=None):
        """Recebe arquivos de trabalhos da atividade, analisa via Gemini e grava relatórios."""
        atividade = self.get_object()
        if not professor_tem_acesso(request.user, atividade):
            return Response(status=status.HTTP_404_NOT_FOUND)

        arquivos = request.FILES.getlist("arquivos")
        if not arquivos and "arquivo" in request.FILES:
            arquivos = [request.FILES["arquivo"]]
        if not arquivos:
            return Response(
                {"arquivos": ["Envie pelo menos um arquivo de trabalho."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            envio = processar_envio_trabalhos(atividade, request.user, arquivos)
        except LLMError as erro:
            return Response({"erro": str(erro)}, status=status.HTTP_502_BAD_GATEWAY)

        saida = EnvioTrabalhosSerializer(envio)
        return Response(saida.data, status=status.HTTP_201_CREATED)
