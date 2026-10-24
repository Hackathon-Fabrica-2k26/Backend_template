from django.db.models import Q, QuerySet
from rest_framework import viewsets

from apps.alunos.models import Responsavel
from apps.alunos.serializers import ResponsavelSerializer


class ResponsavelViewSet(viewsets.ModelViewSet):
    """Responsáveis restritos aos alunos das turmas do professor (LGPD)."""

    serializer_class = ResponsavelSerializer
    search_fields = ["nome"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self) -> QuerySet[Responsavel]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Responsavel.objects.none()
        usuario = self.request.user
        return Responsavel.objects.filter(
            Q(alunos__turma__professores=usuario) | Q(alunos_vinculados__turma__professores=usuario)
        ).distinct()
