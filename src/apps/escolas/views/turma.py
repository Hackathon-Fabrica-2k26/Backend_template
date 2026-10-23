from django.db.models import Count, Q
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
        return (
            Turma.objects.filter(professores=self.request.user)
            .annotate(
                total_estudantes=Count(
                    "alunos",
                    filter=Q(alunos__deleted__isnull=True),
                    distinct=True,
                )
            )
            .distinct()
        )

    def perform_create(self, serializer):
        user = self.request.user
        escola = getattr(user, "escola", None)

        if escola is not None:
            turma = serializer.save(escola=escola)
        else:
            turma = serializer.save()

        turma.professores.add(user)
