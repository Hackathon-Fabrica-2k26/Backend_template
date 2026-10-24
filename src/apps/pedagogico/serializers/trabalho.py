from rest_framework import serializers

from apps.alunos.models import Aluno
from apps.pedagogico.models import Trabalho


class TrabalhoSerializer(serializers.ModelSerializer):
    """Representação de um trabalho avaliado."""

    aluno_nome = serializers.SerializerMethodField()

    class Meta:
        model = Trabalho
        fields = [
            "id",
            "envio",
            "atividade",
            "aluno",
            "aluno_nome",
            "nome_lido",
            "confianca",
            "identificacao",
            "descricao_ia",
            "analise_pedagogica",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "envio",
            "atividade",
            "aluno_nome",
            "nome_lido",
            "confianca",
            "descricao_ia",
            "analise_pedagogica",
            "created_at",
            "updated_at",
        ]

    def get_aluno_nome(self, obj) -> str | None:
        return obj.aluno.nome if obj.aluno else None


class TrabalhoPatchSerializer(serializers.Serializer):
    """Confirmação ou atribuição manual do trabalho ao aluno pela professora."""

    aluno = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.filter(deleted__isnull=True),
        required=False,
        allow_null=True,
    )
    identificacao = serializers.ChoiceField(
        choices=Trabalho.IdentificacaoChoices.choices,
        default=Trabalho.IdentificacaoChoices.CONFIRMADA,
    )
