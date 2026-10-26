from django.contrib.auth import get_user_model
from rest_framework import serializers

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "matricula", "email", "name", "ano", "escola", "otp_ativo"]
        read_only_fields = ["id", "matricula"]
