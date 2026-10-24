"""Endpoint sob demanda de pontos de atenção do aluno (B#45)."""

from drf_spectacular.utils import OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alunos.models import Aluno
from apps.escolas.services.escola_usuario import config_ia_do_usuario
from apps.pedagogico.services.llm import MODELO_PADRAO, LLMError
from apps.pedagogico.services.pontos_atencao import gerar_pontos_atencao_aluno


class PontoAtencaoItemSerializer(serializers.Serializer):
    padrao = serializers.CharField()
    texto = serializers.CharField()
    base_pedagogica = serializers.CharField()
    total_trabalhos = serializers.IntegerField(min_value=1)


class PontosAtencaoRespostaSerializer(serializers.Serializer):
    pontos = PontoAtencaoItemSerializer(many=True)
    disclaimer = serializers.CharField()
    minimo_trabalhos = serializers.IntegerField()
    mensagem = serializers.CharField(required=False)


class AlunoPontosAtencaoView(APIView):
    """Calcula sob demanda os pontos de atenção pedagógicos de um aluno.

    Só chama a IA quando o aluno possui pelo menos 3 Trabalhos analisados
    com `descricao_ia`. Nunca cria Atividade nem emite diagnóstico clínico.
    """

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = PontosAtencaoRespostaSerializer

    @extend_schema(
        summary="Obter pontos de atenção do aluno sob demanda",
        description=(
            "Gera alertas pedagógicos cautelosos para conversa com a família "
            "somente quando o aluno possui 3 ou mais trabalhos analisados com "
            "descrição da IA. Envia ao Gemini apenas os textos `descricao_ia` "
            "anonimizados (sem nome, sem turma e sem datas). Com menos de 3 "
            "trabalhos analisados, devolve 200 com `pontos: []` e mensagem orientativa."
        ),
        parameters=[
            OpenApiParameter(
                name="id",
                type=int,
                location=OpenApiParameter.PATH,
                description="ID do aluno.",
            ),
        ],
        responses={
            200: PontosAtencaoRespostaSerializer,
            404: OpenApiResponse(
                description="Aluno não encontrado ou não pertence às turmas do professor."
            ),
            502: OpenApiResponse(description="Falha ao comunicar com o provedor de IA."),
        },
    )
    def get(self, request, id: int) -> Response:
        aluno = (
            Aluno.objects.filter(
                pk=id,
                turma__professores=request.user,
                deleted__isnull=True,
            )
            .select_related("turma", "turma__escola", "responsavel")
            .first()
        )
        if aluno is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        escola = getattr(request.user, "escola", None) or (
            aluno.turma.escola if aluno.turma else None
        )
        config = config_ia_do_usuario(request.user, escola=escola)

        try:
            resultado = gerar_pontos_atencao_aluno(
                aluno=aluno,
                api_key=config.api_key if config else "",
                modelo=config.modelo if config and config.modelo else MODELO_PADRAO,
            )
        except LLMError as erro:
            return Response(
                {"erro": str(erro)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(resultado, status=status.HTTP_200_OK)
