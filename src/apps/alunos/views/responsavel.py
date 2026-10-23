from django.db.models import QuerySet
from rest_framework import viewsets

from apps.alunos.models import Responsavel
from apps.alunos.serializers import ResponsavelSerializer


class ResponsavelViewSet(viewsets.ModelViewSet):
    """Responsáveis restritos aos alunos das turmas do professor (LGPD)."""

    serializer_class = ResponsavelSerializer
    search_fields = ["nome"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self) -> QuerySet[Responsavel]:
        if getattr(self, "swagger_fake_view", False):
            return Responsavel.objects.none()
        return Responsavel.objects.filter(alunos__turma__professores=self.request.user).distinct()
