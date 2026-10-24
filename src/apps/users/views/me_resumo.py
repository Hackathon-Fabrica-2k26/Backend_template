from drf_spectacular.utils import extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.escolas.models import Turma
from apps.escolas.models.turma import ano_letivo_atual
from apps.pedagogico.models import Atividade, Trabalho

from ..serializers import MeResumoSerializer


class MeResumoView(APIView):
    """Resumo do professor logado para os cards da tela de Perfil."""

    @extend_schema(responses={200: MeResumoSerializer})
    def get(self, request):
        user = request.user
        resumo = {
            "turmas": Turma.objects.filter(
                professores=user, ano_letivo=ano_letivo_atual()
            )
            .distinct()
            .count(),
            "atividades": Atividade.objects.filter(criada_por=user).count(),
            "trabalhos_analisados": Trabalho.objects.filter(
                atividade__turma__professores=user,
                status=Trabalho.StatusChoices.ANALISADO,
            )
            .distinct()
            .count(),
        }
        return Response(MeResumoSerializer(resumo).data)
