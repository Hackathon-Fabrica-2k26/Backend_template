from rest_framework import serializers

from ..models import EnvioTrabalhos, Trabalho


class EnvioTrabalhosSerializer(serializers.ModelSerializer):
    class Meta:
        model = EnvioTrabalhos
        fields = [
            "id",
            "atividade",
            "enviado_por",
            "total_arquivos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "enviado_por", "created_at", "updated_at"]


class TrabalhoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trabalho
        fields = [
            "id",
            "envio",
            "atividade",
            "aluno",
            "variacao",
            "nome_lido",
            "confianca_nome",
            "identificacao",
            "confirmado_por",
            "descricao_ia",
            "dados_analise",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
