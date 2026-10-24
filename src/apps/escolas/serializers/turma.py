
from rest_framework import serializers

from apps.escolas.models import Turma


class TurmaSerializer(serializers.ModelSerializer):
    turno_display = serializers.CharField(source="get_turno_display", read_only=True)
    total_estudantes = serializers.IntegerField(read_only=True, default=0)

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
        ]

    def validate(self, attrs):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        escola_usuario = getattr(user, "escola", None)

        if escola_usuario is None and not attrs.get("escola"):
            raise serializers.ValidationError({
                "escola": "Informe a escola da turma."
            })

        return attrs
    
    def get_fields(self):
        fields = super().get_fields()

        request = self.context.get("request")
        user = getattr(request, "user", None)
        escola_usuario = getattr(user, "escola", None)
        fields["escola"].required = escola_usuario is None
        return fields

