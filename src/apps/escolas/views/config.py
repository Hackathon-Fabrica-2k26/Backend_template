from rest_framework.viewsets import ModelViewSet

from apps.escolas.models import Config
from apps.escolas.serializers import ConfigSerializer


class ConfigViewSet(ModelViewSet):
    queryset = Config.objects.all()
    serializer_class = ConfigSerializer