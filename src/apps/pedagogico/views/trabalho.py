from django.db.models import QuerySet
from rest_framework import viewsets

from apps.pedagogico.models import Trabalho
from apps.pedagogico.serializers import TrabalhoSerializer


class TrabalhoViewSet(viewsets.ReadOnlyModelViewSet):
    """Trabalhos somente leitura restritos às turmas do professor (LGPD)."""

    serializer_class = TrabalhoSerializer
    filterset_fields = ["atividade", "envio", "aluno", "identificacao", "status"]
    ordering_fields = ["created_at"]

    def get_queryset(self) -> QuerySet[Trabalho]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Trabalho.objects.none()
        return Trabalho.objects.filter(
            atividade__turma__professores=self.request.user
        ).distinct()
