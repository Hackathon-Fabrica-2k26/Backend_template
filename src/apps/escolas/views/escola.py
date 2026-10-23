from rest_framework.viewsets import ModelViewSet

from apps.escolas.models import Escola
from apps.escolas.serializers import EscolaSerializer


class EscolaViewSet(ModelViewSet):
    queryset = Escola.objects.all()
    serializer_class = EscolaSerializer