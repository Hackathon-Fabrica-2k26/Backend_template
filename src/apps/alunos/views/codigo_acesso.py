from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alunos.models import Aluno
from apps.alunos.serializers.codigo_acesso import (
    CodigoAcessoGeradoSerializer,
    CodigoAcessoRevogadoSerializer,
)
from apps.alunos.services import gerar_codigo, revogar_codigos_ativos


class _AlunoDaProfessoraMixin:
    def get_aluno(self) -> Aluno:
        return get_object_or_404(
            Aluno.objects.filter(turma__professores=self.request.user).distinct(),  # type: ignore[attr-defined]
            pk=self.kwargs["id"],  # type: ignore[attr-defined]
        )


class AlunoCodigoAcessoView(_AlunoDaProfessoraMixin, APIView):
    """Gera o código de acesso do responsável (8 caracteres, 7 dias) e revoga o anterior."""

    serializer_class = CodigoAcessoGeradoSerializer

    @extend_schema(
        request=None,
        responses={
            201: CodigoAcessoGeradoSerializer,
            404: OpenApiResponse(description="Aluno não encontrado."),
        },
    )
    def post(self, request, id):
        aluno = self.get_aluno()
        codigo, registro = gerar_codigo(aluno, request.user)
        dados = {"codigo": codigo, "gerado_em": registro.gerado_em, "expira_em": registro.expira_em}
        return Response(CodigoAcessoGeradoSerializer(dados).data, status=status.HTTP_201_CREATED)


class AlunoCodigoAcessoRevogarView(_AlunoDaProfessoraMixin, APIView):
    """Revoga os códigos pendentes do aluno."""

    serializer_class = CodigoAcessoRevogadoSerializer

    @extend_schema(
        request=None,
        responses={
            200: CodigoAcessoRevogadoSerializer,
            404: OpenApiResponse(description="Aluno não encontrado."),
        },
    )
    def post(self, request, id):
        aluno = self.get_aluno()
        return Response({"revogados": revogar_codigos_ativos(aluno)})
