from rest_framework import serializers

from ..models import Atividade


class AtividadeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Atividade
        fields = [
            "id",
            "turma",
            "criada_por",
            "titulo",
            "origem",
            "texto_original",
            "objetivo",
            "status",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "criada_por", "created_at", "updated_at"]

    def validate_turma(self, turma):
        """A turma precisa pertencer ao professor logado."""
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            if not turma.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode vincular atividades às suas turmas."
                )
        return turma
