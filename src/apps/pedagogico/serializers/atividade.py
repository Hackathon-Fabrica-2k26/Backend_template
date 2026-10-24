from rest_framework import serializers

from ..models import Atividade


class AtividadeSerializer(serializers.ModelSerializer):
    descricao = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

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
            "descricao",
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

    def validate(self, attrs):
        descricao = attrs.pop("descricao", None)
        if descricao is not None and not attrs.get("objetivo"):
            attrs["objetivo"] = descricao
        return attrs
