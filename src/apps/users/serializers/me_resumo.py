from rest_framework import serializers


class MeResumoSerializer(serializers.Serializer):
    turmas = serializers.IntegerField()
    atividades = serializers.IntegerField()
    trabalhos_analisados = serializers.IntegerField()
