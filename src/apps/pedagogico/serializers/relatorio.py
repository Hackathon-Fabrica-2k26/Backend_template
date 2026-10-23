from rest_framework import serializers

from ..models import Relatorio


class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = ["id", "aluno", "dados", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
