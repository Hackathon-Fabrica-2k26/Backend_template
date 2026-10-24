from rest_framework import serializers

from apps.alunos.models import Aluno
from apps.alunos.services import tem_consentimento_ativo
from apps.pedagogico.models import Trabalho


class TrabalhoSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source="aluno.nome", read_only=True, default=None)

    class Meta:
        model = Trabalho
        fields = [
            "id",
            "envio",
            "atividade",
            "aluno",
            "aluno_nome",
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
        read_only_fields = [
            "id",
            "envio",
            "atividade",
            "aluno_nome",
            "nome_lido",
            "confianca_nome",
            "confirmado_por",
            "descricao_ia",
            "dados_analise",
            "status",
            "created_at",
            "updated_at",
        ]


class TrabalhoConfirmacaoSerializer(serializers.Serializer):
    aluno = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.all(),
        required=True,
        help_text="ID do aluno confirmado para este trabalho.",
    )
    identificacao = serializers.ChoiceField(
        choices=[
            (
                Trabalho.IdentificacaoChoices.CONFIRMADA,
                Trabalho.IdentificacaoChoices.CONFIRMADA.label,
            ),
        ],
        default=Trabalho.IdentificacaoChoices.CONFIRMADA,
        required=False,
    )

    def validate_aluno(self, aluno: Aluno) -> Aluno:
        trabalho: Trabalho | None = self.context.get("trabalho")
        if trabalho is not None:
            turma_atividade = trabalho.atividade.turma
            if turma_atividade and aluno.turma_id != turma_atividade.pk:
                raise serializers.ValidationError(
                    "O aluno informado não pertence à turma desta atividade."
                )
        if not tem_consentimento_ativo(aluno):
            raise serializers.ValidationError(
                "Aluno sem consentimento ativo do responsável para uso de IA."
            )
        return aluno
