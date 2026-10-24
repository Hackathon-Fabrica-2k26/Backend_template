from django.db.models import QuerySet
from rest_framework import viewsets

from apps.pedagogico.models import PerfilApoio
from apps.pedagogico.serializers import PerfilApoioSerializer


class PerfilApoioViewSet(viewsets.ModelViewSet):
    """Perfis de apoio restritos aos alunos das turmas do professor (LGPD)."""

    serializer_class = PerfilApoioSerializer
    filterset_fields = ["aluno", "ativo"]
    ordering_fields = ["created_at"]

    def get_queryset(self) -> QuerySet[PerfilApoio]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return PerfilApoio.objects.none()
        return PerfilApoio.objects.filter(aluno__turma__professores=self.request.user).distinct()
