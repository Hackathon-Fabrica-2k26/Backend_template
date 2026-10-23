from django.db.models import QuerySet
from rest_framework import viewsets

from apps.pedagogico.models import Relatorio
from apps.pedagogico.serializers import RelatorioSerializer


class RelatorioViewSet(viewsets.ModelViewSet):
    """Relatórios restritos aos alunos das turmas do professor (LGPD)."""

    serializer_class = RelatorioSerializer
    filterset_fields = ["aluno"]
    ordering_fields = ["created_at"]

    def get_queryset(self) -> QuerySet[Relatorio]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Relatorio.objects.none()
        return Relatorio.objects.filter(aluno__turma__professores=self.request.user).distinct()
