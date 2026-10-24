from datetime import date

from drf_spectacular.utils import extend_schema_field, inline_serializer
from rest_framework import serializers

from apps.escolas.models import Turma

from ..models import Aluno


class AlunoSerializer(serializers.ModelSerializer):
    turma = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all(),
        required=True,
        allow_null=False,
    )
    idade = serializers.SerializerMethodField(read_only=True)
    resumo = serializers.SerializerMethodField(read_only=True)

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
            "resumo",
        ]
        read_only_fields = ["id", "idade", "resumo"]

    @extend_schema_field(serializers.IntegerField(allow_null=True))
    def get_idade(self, obj: Aluno) -> int | None:
        if not obj.nascimento:
            return None
        hoje = date.today()
        return (
            hoje.year
            - obj.nascimento.year
            - ((hoje.month, hoje.day) < (obj.nascimento.month, obj.nascimento.day))
        )

    @extend_schema_field(
        inline_serializer(
            name="AlunoResumo",
            fields={
                "relatorios": serializers.IntegerField(),
                "trabalhos": serializers.IntegerField(),
                "observacoes_pendentes": serializers.IntegerField(),
            },
        )
    )
    def get_resumo(self, obj: Aluno) -> dict[str, int]:
        total_relatorios = getattr(obj, "total_relatorios", None)
        if total_relatorios is None:
            total_relatorios = obj.relatorios.filter(deleted__isnull=True).count()

        total_trabalhos = getattr(obj, "total_trabalhos", None)
        if total_trabalhos is None:
            total_trabalhos = obj.trabalhos.filter(deleted__isnull=True).count()

        return {
            "relatorios": total_relatorios,
            "trabalhos": total_trabalhos,
            "observacoes_pendentes": 0,
        }

    def validate_turma(self, value):
        """A turma precisa pertencer a um dos professores logados."""
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            if not value.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError("Você só pode cadastrar alunos em turmas suas.")
        return value
