from django.utils import timezone
from rest_framework import serializers

from apps.escolas.models import Turma

from ..models import Aluno


class AlunoSerializer(serializers.ModelSerializer):
    idade = serializers.SerializerMethodField()
    turma = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all(),
        required=True,
        allow_null=False,
    )

    class Meta:
        model = Aluno
        fields = [
            "id",
            "nome",
            "matricula",
            "nascimento",
            "idade",
            "ativo",
            "turma",
            "meta_dados",
            "responsavel",
        ]
        read_only_fields = ["id"]

    def get_idade(self, obj):
        if obj.nascimento is None:
            return None

        hoje = timezone.localdate()
        return hoje.year - obj.nascimento.year - (
            (hoje.month, hoje.day) < (obj.nascimento.month, obj.nascimento.day)
        )

    def validate_turma(self, value):
        """A turma precisa pertencer a um dos professores logados."""
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            if not value.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode cadastrar alunos em turmas suas."
                )
        return value
