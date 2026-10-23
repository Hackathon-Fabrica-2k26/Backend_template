
from rest_framework import serializers

from apps.escolas.models import Turma


class TurmaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Turma
        fields = [
            "id", 
            "nome", 
            "escola", 
            "professores",
            ]
