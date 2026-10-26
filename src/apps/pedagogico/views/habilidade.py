from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.pedagogico.services.habilidades import HABILIDADES


class HabilidadeListView(APIView):
    """Lista fixa de habilidades do 1º ano (referência BNCC) usada nos trabalhos e no reforço."""

    @extend_schema(
        responses=inline_serializer(
            name="Habilidade",
            fields={
                "codigo": serializers.CharField(),
                "area": serializers.CharField(),
                "nome": serializers.CharField(),
            },
            many=True,
        )
    )
    def get(self, request):
        return Response(HABILIDADES)
