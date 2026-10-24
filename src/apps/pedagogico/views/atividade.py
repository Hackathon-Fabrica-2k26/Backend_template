from django.db.models import QuerySet
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.pedagogico.models import Atividade
from apps.pedagogico.serializers import (
    AtividadeSerializer,
    AtividadeVariacaoSerializer,
    MapaVariacaoItemSerializer,
)
from apps.pedagogico.services import (
    MODELO_PADRAO,
    LLMError,
    gerar_variacoes_atividade,
)


class AtividadeViewSet(viewsets.ModelViewSet):
    """Atividades restritas às turmas do professor (LGPD)."""

    serializer_class = AtividadeSerializer
    filterset_fields = ["turma", "status", "origem"]
    search_fields = ["titulo", "objetivo"]
    ordering_fields = ["titulo", "created_at"]

    def get_queryset(self) -> QuerySet[Atividade]:  # type: ignore
        if getattr(self, "swagger_fake_view", False):
            return Atividade.objects.none()
        return Atividade.objects.filter(turma__professores=self.request.user).distinct()

    def perform_create(self, serializer):
        serializer.save(criada_por=self.request.user)

    @extend_schema(
        request=None,
        responses={201: AtividadeVariacaoSerializer(many=True)},
    )
    @action(detail=True, methods=["post"], url_path="gerar-variacoes")
    def gerar_variacoes(self, request, pk=None):
        atividade = self.get_object()
        escola = getattr(request.user, "escola", None) or atividade.turma.escola
        config = getattr(escola, "config", None) if escola else None

        try:
            variacoes = gerar_variacoes_atividade(
                atividade=atividade,
                api_key=config.api_key if config else "",
                modelo=config.modelo if config and config.modelo else MODELO_PADRAO,
            )
        except LLMError as erro:
            return Response(
                {"erro": str(erro)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        saida = AtividadeVariacaoSerializer(
            variacoes,
            many=True,
            context={"request": request},
        )
        return Response(saida.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        responses={200: MapaVariacaoItemSerializer(many=True)},
    )
    @action(detail=True, methods=["get"], url_path="mapa-variacoes")
    def mapa_variacoes(self, request, pk=None):
        atividade = self.get_object()
        variacoes = atividade.variacoes.order_by("numero")
        dados = [
            {
                "variacao_id": variacao.id,
                "numero": variacao.numero,
                "rotulo": variacao.rotulo,
                "eh_geral": variacao.eh_geral,
                "status": variacao.status,
                "alunos": [
                    {
                        "id": atribuicao.aluno.id,
                        "nome": atribuicao.aluno.nome,
                    }
                    for atribuicao in variacao.atribuicoes.filter(
                        deleted__isnull=True
                    ).select_related("aluno")
                ],
            }
            for variacao in variacoes
        ]
        return Response(dados, status=status.HTTP_200_OK)
