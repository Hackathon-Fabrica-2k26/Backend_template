import re

from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.alunos.models import Aluno
from apps.escolas.models import Turma
from apps.escolas.serializers import TurmaSerializer
from apps.escolas.serializers.turma import limpar_nome_aluno
from apps.escolas.services.escola_usuario import escola_do_usuario
from apps.pedagogico.serializers import HabilidadeTurmaSerializer
from apps.pedagogico.services import calcular_habilidades_turma


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

    @extend_schema(
        summary="Resumo de habilidades a reforçar da turma",
        description=(
            "Retorna para cada habilidade da lista fixa (1º ano BNCC) o total de alunos da turma "
            "que estão em reforço (>= 2 trabalhos a reforçar). Apenas alunos com consentimento ativo "
            "são contabilizados e nenhum nome é incluído na resposta agregada (LGPD)."
        ),
        responses={
            200: HabilidadeTurmaSerializer(many=True),
            404: {"description": "Turma não encontrada ou não pertence ao professor."},
        },
    )
    @action(detail=True, methods=["get"], url_path="habilidades")
    def habilidades(self, request, pk=None):
        turma = get_object_or_404(self.get_queryset(), pk=pk)
        dados = calcular_habilidades_turma(turma)
        return Response(dados, status=status.HTTP_200_OK)

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
