from rest_framework import serializers

from ..models import Aluno


class AlunoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aluno
        fields = [
            "id",
            "nome",
            "meta_dados",
            "responsavel",
        ]
        read_only_fields = ["id"]