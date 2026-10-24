from rest_framework import serializers

from apps.pedagogico.models import EnvioTrabalhos
from apps.pedagogico.serializers.trabalho import TrabalhoSerializer


class TrabalhoUploadSerializer(serializers.Serializer):
    """Validação da lista de arquivos enviados para a atividade."""

    arquivos = serializers.ListField(
        child=serializers.FileField(),
        allow_empty=False,
        required=True,
    )


class EnvioTrabalhosSerializer(serializers.ModelSerializer):
    """Representação detalhada de um lote de envio de trabalhos."""

    trabalhos = TrabalhoSerializer(many=True, read_only=True)

    class Meta:
        model = EnvioTrabalhos
        fields = [
            "id",
            "atividade",
            "enviado_por",
            "total_arquivos",
            "status",
            "trabalhos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "atividade",
            "enviado_por",
            "total_arquivos",
            "status",
            "trabalhos",
            "created_at",
            "updated_at",
        ]
