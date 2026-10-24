from django.db.models import QuerySet
from rest_framework import viewsets

from apps.pedagogico.models import AtividadeVariacao
from apps.pedagogico.serializers import AtividadeVariacaoSerializer


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
