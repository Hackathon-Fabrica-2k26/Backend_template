from rest_framework import serializers

from apps.alunos.models import Aluno

from ..models import AtividadeVariacao, VariacaoAluno


class MapaVariacaoAlunoSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nome = serializers.CharField()


class MapaVariacaoItemSerializer(serializers.Serializer):
    variacao_id = serializers.IntegerField()
    numero = serializers.IntegerField()
    rotulo = serializers.CharField()
    eh_geral = serializers.BooleanField()
    status = serializers.CharField()
    alunos = MapaVariacaoAlunoSerializer(many=True)


class AtividadeVariacaoSerializer(serializers.ModelSerializer):
    alunos = serializers.PrimaryKeyRelatedField(
        queryset=Aluno.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = AtividadeVariacao
        fields = [
            "id",
            "atividade",
            "numero",
            "rotulo",
            "eh_geral",
            "conteudo",
            "status",
            "editada_manual",
            "aprovada_por",
            "aprovada_em",
            "alunos",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "aprovada_por",
            "aprovada_em",
            "created_at",
            "updated_at",
        ]

    def validate_atividade(self, atividade):
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            if not atividade.turma.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode vincular variações a atividades das suas turmas."
                )
        return atividade

    def validate(self, attrs):
        atividade = attrs.get("atividade") or getattr(self.instance, "atividade", None)
        alunos = attrs.get("alunos")
        if atividade is not None and alunos:
            for aluno in alunos:
                if aluno.turma_id != atividade.turma_id:
                    raise serializers.ValidationError(
                        {"alunos": "Todos os alunos devem pertencer à turma da atividade."}
                    )
        return attrs

    def create(self, validated_data):
        alunos = validated_data.pop("alunos", None)
        variacao = super().create(validated_data)
        if alunos:
            for aluno in alunos:
                VariacaoAluno.objects.get_or_create(variacao=variacao, aluno=aluno)
        return variacao

    def update(self, instance, validated_data):
        alunos = validated_data.pop("alunos", None)
        if "conteudo" in validated_data and "editada_manual" not in validated_data:
            validated_data["editada_manual"] = True
        variacao = super().update(instance, validated_data)
        if alunos is not None:
            ids_novos = {aluno.pk for aluno in alunos}
            VariacaoAluno.objects.filter(variacao=variacao).exclude(
                aluno_id__in=ids_novos
            ).delete()
            for aluno in alunos:
                VariacaoAluno.objects.get_or_create(variacao=variacao, aluno=aluno)
        return variacao
