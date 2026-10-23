from rest_framework import viewsets

from apps.alunos.models import Aluno
from apps.alunos.serializers import AlunoSerializer


class AlunoViewSet(viewsets.ModelViewSet):
    serializer_class = AlunoSerializer
    filterset_fields = ["turma"]
    search_fields = ["nome"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Aluno.objects.none()
        return Aluno.objects.filter(turma__professores=self.request.user).distinct()
