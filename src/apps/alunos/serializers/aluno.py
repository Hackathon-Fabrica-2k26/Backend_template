from rest_framework import serializers

from apps.escolas.models import Turma

from ..models import Aluno


class AlunoSerializer(serializers.ModelSerializer):
    turma = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all(),
        required=True,
        allow_null=False,
    )

    class Meta:
        model = Aluno
        fields = ["id", "nome", "turma", "meta_dados", "responsavel"]
        read_only_fields = ["id"]

    def validate_turma(self, value):
        """A turma precisa pertencer a um dos professores logados."""
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            if not value.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode cadastrar alunos em turmas suas."
                )
        return value
