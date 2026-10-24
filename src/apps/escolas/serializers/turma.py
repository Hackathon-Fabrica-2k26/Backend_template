import re

from rest_framework import serializers

from apps.escolas.models import Turma

MAX_ALUNOS_POR_TURMA = 60
MAX_TAMANHO_NOME_ALUNO = 120


def limpar_nome_aluno(nome: str) -> str:
    """Normaliza espaços internos e valida o limite de 120 caracteres."""
    nome_limpo = re.sub(r"\s+", " ", str(nome)).strip()
    if len(nome_limpo) > MAX_TAMANHO_NOME_ALUNO:
        raise serializers.ValidationError(
            {"alunos": [f"Cada nome deve ter no máximo {MAX_TAMANHO_NOME_ALUNO} caracteres."]}
        )
    return nome_limpo


class TurmaSerializer(serializers.ModelSerializer):
    turno_display = serializers.CharField(source="get_turno_display", read_only=True)
    total_estudantes = serializers.IntegerField(read_only=True, default=0)
    alunos = serializers.ListField(
        child=serializers.CharField(allow_blank=True, trim_whitespace=False),
        write_only=True,
        required=False,
        max_length=MAX_ALUNOS_POR_TURMA,
        help_text="Lista opcional de nomes de estudantes (máx. 60) para criar junto com a turma.",
    )

    class Meta:
        model = Turma
        fields = [
            "id",
            "nome",
            "turno",
            "turno_display",
            "ano_letivo",
            "total_estudantes",
            "escola",
            "professores",
            "alunos",
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        escola_usuario = getattr(user, "escola", None)

        if escola_usuario is None and not attrs.get("escola"):
            raise serializers.ValidationError({"escola": "Informe a escola da turma."})

        return attrs

    def get_fields(self):
        fields = super().get_fields()

        request = self.context.get("request")
        user = getattr(request, "user", None)
        escola_usuario = getattr(user, "escola", None)
        fields["escola"].required = escola_usuario is None
        return fields
