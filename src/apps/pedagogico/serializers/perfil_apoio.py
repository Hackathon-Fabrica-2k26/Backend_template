from rest_framework import serializers

from ..models import PerfilApoio


class PerfilApoioSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerfilApoio
        fields = [
            "id",
            "aluno",
            "necessidades",
            "estrategias",
            "observacoes",
            "ativo",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_aluno(self, aluno):
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            turma = aluno.turma
            if turma is None or not turma.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode gerenciar perfis de apoio de alunos das suas turmas."
                )
        return aluno

    def validate(self, attrs):
        aluno = attrs.get("aluno") or getattr(self.instance, "aluno", None)
        ativo = attrs.get("ativo", getattr(self.instance, "ativo", True))
        if aluno is not None and ativo:
            qs = PerfilApoio.objects.filter(aluno=aluno, ativo=True)
            if self.instance is not None:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    {"ativo": "Este aluno já possui um perfil de apoio ativo."}
                )
        return attrs
