from rest_framework import viewsets

from apps.escolas.models import Escola
from apps.escolas.serializers import EscolaSerializer


class EscolaViewSet(viewsets.ModelViewSet):
    serializer_class = EscolaSerializer
    filterset_fields = ["config"]
    search_fields = ["nome", "endereco"]
    ordering_fields = ["nome", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Escola.objects.none()
        return Escola.objects.filter(turmas__professores=self.request.user).distinct()
