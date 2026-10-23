from rest_framework import viewsets

from apps.escolas.models import Turma
from apps.escolas.serializers import TurmaSerializer


class TurmaViewSet(viewsets.ModelViewSet):
    serializer_class = TurmaSerializer
    filterset_fields = ["escola"]
    search_fields = ["nome"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Turma.objects.none()
        return Turma.objects.filter(professores=self.request.user).distinct()

    def perform_create(self, serializer):
        turma = serializer.save()
        if self.request.user.is_authenticated:
            turma.professores.add(self.request.user)
