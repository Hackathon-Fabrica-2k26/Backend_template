from rest_framework import serializers

from ..models import Atividade


class AtividadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Atividade
        fields = ["id", "aluno", "nome", "tipo", "relatorios", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
