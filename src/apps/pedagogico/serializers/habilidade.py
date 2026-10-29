from rest_framework import serializers


class HabilidadeAlunoSerializer(serializers.Serializer):
    codigo = serializers.CharField(help_text="Código da habilidade na BNCC.")
    area = serializers.CharField(help_text="Área de conhecimento.")
    nome = serializers.CharField(help_text="Descrição pedagógica da habilidade.")
    trabalhos_a_reforcar = serializers.IntegerField(
        min_value=0,
        help_text="Quantidade de trabalhos em que a habilidade foi identificada a reforçar.",
    )
    trabalhos_demonstrada = serializers.IntegerField(
        min_value=0,
        help_text="Quantidade de trabalhos em que a habilidade foi demonstrada.",
    )
    em_reforco = serializers.BooleanField(
        help_text="True se a habilidade apareceu como a reforçar em 2 ou mais trabalhos.",
    )
    ultimo_trabalho_em = serializers.DateTimeField(
        allow_null=True,
        help_text="Data do último trabalho em que a habilidade foi observada.",
    )


class HabilidadeTurmaSerializer(serializers.Serializer):
    codigo = serializers.CharField(help_text="Código da habilidade na BNCC.")
    area = serializers.CharField(help_text="Área de conhecimento.")
    nome = serializers.CharField(help_text="Descrição pedagógica da habilidade.")
    total_alunos_reforco = serializers.IntegerField(
        min_value=0,
        help_text="Quantidade de alunos da turma com esta habilidade em reforço.",
    )
    alunos_em_reforco = serializers.IntegerField(
        min_value=0,
        help_text="Alias de total_alunos_reforco.",
    )
