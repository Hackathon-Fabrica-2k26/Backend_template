from rest_framework import serializers

from ..models import Relatorio


class RelatorioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Relatorio
        fields = ["id", "aluno", "dados", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_aluno(self, aluno):
        """O aluno precisa pertencer a uma das turmas do professor logado."""
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            turma = aluno.turma
            if turma is None or not turma.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode vincular relatórios a alunos das suas turmas."
                )
        return aluno
