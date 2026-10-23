from rest_framework import serializers

from apps.escolas.models import Escola


class EscolaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Escola
        fields = [
            "id",
            "nome",
            "endereco",
            "config",
        ]
