from rest_framework.viewsets import ModelViewSet

from apps.escolas.models import Turma
from apps.escolas.serializers import TurmaSerializer


class TurmaViewSet(ModelViewSet):
    queryset = Turma.objects.all()
    serializer_class = TurmaSerializer