from rest_framework import generics
from rest_framework.permissions import IsAuthenticated

from apps.pedagogico.serializers import RelatorioSerializer


class RelatoriosAlunoView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RelatorioSerializer

    def get_queryset(self):
        ...