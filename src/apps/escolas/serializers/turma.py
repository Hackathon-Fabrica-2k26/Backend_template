from rest_framework import serializers

from apps.escolas.models import Turma


class TurmaSerializer(serializers.ModelSerializer):
    turno_display = serializers.CharField(source="get_turno_display", read_only=True)
    total_estudantes = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Turma
        fields = [
            "id",
            "nome",
            "turno",
            "turno_display",
            "total_estudantes",
            "escola",
            "professores",
        ]
