from django.db.models import QuerySet
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.alunos.models import Consentimento
from apps.alunos.serializers import ConsentimentoSerializer
from apps.alunos.services import revogar_consentimento


class ConsentimentoViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Consentimento do responsável; a revogação apaga os dados derivados da IA."""

    serializer_class = ConsentimentoSerializer
    filterset_fields = ["aluno", "finalidade"]
    search_fields = ["aluno__nome"]
    ordering_fields = ["aceito_em", "created_at"]

    def get_queryset(self) -> QuerySet[Consentimento]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Consentimento.objects.none()
        return Consentimento.objects.filter(aluno__turma__professores=self.request.user).distinct()

    @action(detail=True, methods=["post"])
    def revogar(self, request, pk=None):
        consentimento = self.get_object()
        if not consentimento.ativo:
            return Response(
                {"erro": "Consentimento já revogado."}, status=status.HTTP_400_BAD_REQUEST
            )
        revogar_consentimento(consentimento)
        return Response(self.get_serializer(consentimento).data)
