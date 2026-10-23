from django.db.models import QuerySet
from rest_framework import viewsets

from apps.pedagogico.models import Atividade
from apps.pedagogico.serializers import AtividadeSerializer


class AtividadeViewSet(viewsets.ModelViewSet):
    """Atividades restritas aos alunos das turmas do professor (LGPD)."""

    serializer_class = AtividadeSerializer
    filterset_fields = ["aluno"]
    search_fields = ["nome"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self) -> QuerySet[Atividade]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Atividade.objects.none()
        return Atividade.objects.filter(aluno__turma__professores=self.request.user).distinct()
