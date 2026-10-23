from rest_framework import serializers

from ..models import MetaDados


class MetaDadosSerializer(serializers.ModelSerializer):
    class Meta:
        model = MetaDados
        fields = ["id", "perfil_disc", "caracteristicas"]