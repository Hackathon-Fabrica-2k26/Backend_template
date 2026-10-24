from rest_framework import serializers

from ..models import Responsavel


class ResponsavelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Responsavel
        fields = ["id", "nome", "email", "telefone", "cpf"]
