from rest_framework import serializers


class CodigoAcessoGeradoSerializer(serializers.Serializer):
    codigo = serializers.CharField(read_only=True, help_text="Exibido apenas nesta resposta.")
    gerado_em = serializers.DateTimeField(read_only=True)
    expira_em = serializers.DateTimeField(read_only=True)


class CodigoAcessoRevogadoSerializer(serializers.Serializer):
    revogados = serializers.IntegerField(read_only=True)


class ResponsavelAcessoSerializer(serializers.Serializer):
    codigo = serializers.CharField(max_length=32, write_only=True)
    nome = serializers.CharField(max_length=100, write_only=True)
    email = serializers.EmailField(
        max_length=255, required=False, allow_blank=True, write_only=True
    )
    parentesco = serializers.CharField(
        max_length=30, required=False, allow_blank=True, write_only=True
    )


class ResponsavelTokenSerializer(serializers.Serializer):
    token = serializers.CharField(read_only=True)
    tipo = serializers.CharField(read_only=True)
    expira_em_segundos = serializers.IntegerField(read_only=True)


class ResponsavelAlunoSerializer(serializers.Serializer):
    nome = serializers.CharField(read_only=True)
    turma = serializers.CharField(read_only=True, allow_null=True)
    consentimento_ativo = serializers.BooleanField(read_only=True)


class ResponsavelConsentimentoSerializer(serializers.Serializer):
    consentimento_ativo = serializers.BooleanField(read_only=True)
    aceito_em = serializers.DateTimeField(read_only=True, allow_null=True)
    revogado_em = serializers.DateTimeField(read_only=True, allow_null=True)
