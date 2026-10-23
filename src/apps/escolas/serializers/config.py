from rest_framework import serializers

from apps.escolas.models import Config


class ConfigSerializer(serializers.ModelSerializer):
    api_key = serializers.CharField(
        max_length=255,
        write_only=True,
    )

    class Meta:
        model = Config
        fields = [
            "id",
            "api_key",
            "modelo",
            "campos_form",
        ]
