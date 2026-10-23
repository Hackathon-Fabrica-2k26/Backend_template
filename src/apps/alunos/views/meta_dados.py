from django.db.models import QuerySet
from rest_framework import viewsets

from apps.alunos.models import MetaDados
from apps.alunos.serializers import MetaDadosSerializer


class MetaDadosViewSet(viewsets.ModelViewSet):
    """Metadados restritos aos alunos das turmas do professor (LGPD)."""

    serializer_class = MetaDadosSerializer
    ordering_fields = ["created_at"]

    def get_queryset(self) -> QuerySet[MetaDados]: # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return MetaDados.objects.none()
        return MetaDados.objects.filter(
            aluno__turma__professores=self.request.user
        ).distinct()
