import re

from django.db import transaction
from django.db.models import Count, Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import viewsets

from apps.alunos.models import Aluno
from apps.escolas.models import Turma
from apps.escolas.serializers import TurmaSerializer
from apps.escolas.serializers.turma import limpar_nome_aluno
from apps.escolas.services.escola_usuario import escola_do_usuario


@extend_schema_view(
    create=extend_schema(
        request=TurmaSerializer,
        responses={201: TurmaSerializer, 400: OpenApiTypes.OBJECT},
    ),
)
class TurmaViewSet(viewsets.ModelViewSet):
    serializer_class = TurmaSerializer
    filterset_fields = ["escola", "ano_letivo"]
    search_fields = ["nome"]
    ordering_fields = ["nome", "ano_letivo", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Turma.objects.none()
        return (
            Turma.objects.filter(professores=self.request.user)
            .annotate(
                total_estudantes=Count(
                    "alunos",
                    filter=Q(alunos__deleted__isnull=True, alunos__ativo=True),
                    distinct=True,
                )
            )
            .distinct()
        )

    @transaction.atomic
    def perform_create(self, serializer):
        user = self.request.user
        escola = escola_do_usuario(user)
        nomes_brutos = serializer.validated_data.pop("alunos", None) or []

        if escola is not None:
            turma = serializer.save(escola=escola)
        else:
            turma = serializer.save()

        turma.professores.add(user)

        vistos: set[str] = set()
        criados = 0
        for item in nomes_brutos:
            nome_limpo = limpar_nome_aluno(item)
            if not nome_limpo:
                continue
            chave = re.sub(r"\s+", "", nome_limpo).casefold()
            if chave in vistos:
                continue
            vistos.add(chave)
            Aluno.objects.create(nome=nome_limpo, turma=turma)
            criados += 1

        turma.total_estudantes = criados
