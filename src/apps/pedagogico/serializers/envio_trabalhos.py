from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.pedagogico.models import EnvioTrabalhos, Trabalho

from .trabalho import TrabalhoSerializer


class EnvioTrabalhosUploadSerializer(serializers.Serializer):
    arquivos = serializers.ListField(
        child=serializers.FileField(allow_empty_file=False),
        allow_empty=False,
        help_text="Lista de arquivos (PDF, PNG, JPG, WEBP ou DOCX) com até 20 MB cada.",
    )


class EnvioTrabalhosSerializer(serializers.ModelSerializer):
    trabalhos = TrabalhoSerializer(many=True, read_only=True)
    status = serializers.SerializerMethodField()

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
        read_only_fields = fields

    @extend_schema_field(serializers.CharField())
    def get_status(self, obj: EnvioTrabalhos) -> str:
        if obj.trabalhos.filter(identificacao=Trabalho.IdentificacaoChoices.PENDENTE).exists():
            return "revisao_pendente"
        return "concluido"
