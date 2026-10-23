from rest_framework import viewsets

from apps.escolas.models import Config
from apps.escolas.serializers import ConfigSerializer


class ConfigViewSet(viewsets.ModelViewSet):
    serializer_class = ConfigSerializer
    search_fields = ["modelo"]
    ordering_fields = ["modelo", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Config.objects.none()
        return Config.objects.filter(escolas__turmas__professores=self.request.user).distinct()
