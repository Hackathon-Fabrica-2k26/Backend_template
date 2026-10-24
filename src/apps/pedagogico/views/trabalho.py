from django.db.models import Q, QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.pedagogico.models import Trabalho
from apps.pedagogico.serializers import TrabalhoPatchSerializer, TrabalhoSerializer
from apps.pedagogico.services import confirmar_trabalho, obter_alunos_da_atividade


class TrabalhoViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Trabalhos escolares com isolamento por professor (LGPD)."""

    serializer_class = TrabalhoSerializer
    filterset_fields = ["atividade", "aluno", "identificacao"]
    search_fields = ["nome_lido", "aluno__nome", "descricao_ia"]
    ordering_fields = ["confianca", "created_at"]

    def get_queryset(self) -> QuerySet[Trabalho]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Trabalho.objects.none()

        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Trabalho.objects.all()

        filtro = Q(atividade__aluno__turma__professores=user) | Q(envio__enviado_por=user)
        if hasattr(Trabalho, "atividade") and any(
            f.name == "turma"
            for f in Trabalho._meta.get_field("atividade").related_model._meta.fields
        ):
            filtro |= Q(atividade__turma__professores=user)

        return Trabalho.objects.filter(filtro).distinct()

    @extend_schema(
        request=TrabalhoPatchSerializer,
        responses={200: TrabalhoSerializer},
    )
    def partial_update(self, request, *args, **kwargs):
        """Confirma ou atribui manualmente o aluno ao trabalho."""
        instance = self.get_object()
        serializer = TrabalhoPatchSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)

        aluno = serializer.validated_data.get("aluno") or instance.aluno
        if aluno is None:
            raise ValidationError(
                {"aluno": "É necessário informar o aluno para confirmar o trabalho."}
            )

        # Validação: aluno deve pertencer à turma da atividade
        alunos_permitidos = obter_alunos_da_atividade(instance.atividade)
        if alunos_permitidos and aluno not in alunos_permitidos:
            raise ValidationError(
                {"aluno": "O aluno selecionado não pertence à turma desta atividade."}
            )

        identificacao = serializer.validated_data.get(
            "identificacao", Trabalho.IdentificacaoChoices.CONFIRMADA
        )
        trabalho_atualizado = confirmar_trabalho(instance, aluno, identificacao=identificacao)

        saida = self.get_serializer(trabalho_atualizado)
        return Response(saida.data, status=status.HTTP_200_OK)
