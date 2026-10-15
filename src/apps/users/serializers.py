from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                lookup="iexact",
                message="Já existe um usuário com este e-mail.",
            )
        ]
    )
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["id", "email", "name", "password"]

    def validate(self, attrs):
        usuario = User(email=attrs.get("email", ""), name=attrs.get("name", ""))
        try:
            validate_password(attrs["password"], usuario)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)}) from exc
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "name"]
