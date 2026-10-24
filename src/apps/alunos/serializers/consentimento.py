from django.utils import timezone
from rest_framework import serializers

from ..models import Consentimento
from ..models.consentimento import FINALIDADE_PADRAO


class ConsentimentoSerializer(serializers.ModelSerializer):
    ativo = serializers.BooleanField(read_only=True)

    class Meta:
        model = Consentimento
        fields = [
            "id",
            "aluno",
            "responsavel",
            "finalidade",
            "versao_texto",
            "aceito_em",
            "revogado_em",
            "ativo",
        ]
        read_only_fields = ["responsavel", "aceito_em", "revogado_em"]

    def validate_aluno(self, aluno):
        request = self.context.get("request")
        turma = aluno.turma
        if request and (turma is None or not turma.professores.filter(pk=request.user.pk).exists()):
            raise serializers.ValidationError("Aluno inválido.")
        return aluno

    def validate(self, attrs):
        finalidade = attrs.get("finalidade", FINALIDADE_PADRAO)
        if Consentimento.objects.filter(
            aluno=attrs["aluno"], finalidade=finalidade, revogado_em__isnull=True
        ).exists():
            raise serializers.ValidationError("Já existe consentimento ativo para este aluno.")
        return attrs

    def create(self, validated_data):
        validated_data["responsavel"] = validated_data["aluno"].responsavel
        validated_data["aceito_em"] = timezone.now()
        return super().create(validated_data)
