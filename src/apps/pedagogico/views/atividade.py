from django.db.models import QuerySet
from rest_framework import viewsets

from apps.pedagogico.models import Atividade
from apps.pedagogico.serializers import AtividadeSerializer


class AtividadeViewSet(viewsets.ModelViewSet):
    """Atividades restritas às turmas do professor (LGPD)."""

    serializer_class = AtividadeSerializer
    filterset_fields = ["turma", "status", "origem"]
    search_fields = ["titulo", "objetivo"]
    ordering_fields = ["titulo", "created_at"]

    def get_queryset(self) -> QuerySet[Atividade]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Atividade.objects.none()
        return Atividade.objects.filter(turma__professores=self.request.user).distinct()

    def perform_create(self, serializer):
        serializer.save(criada_por=self.request.user)
