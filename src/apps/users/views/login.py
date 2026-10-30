from django.contrib.auth import authenticate
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from ..services.otp import create_otp
from ..services.otp_email import enviar_email_otp


def mask_email(email):
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

    @extend_schema(
        request=inline_serializer(
            name="LoginRequest",
            fields={
                "matricula": serializers.CharField(),
                "password": serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="LoginOTPResponse",
                fields={
                    "otp_required": serializers.BooleanField(),
                    "otp_token": serializers.CharField(required=False),
                    "email": serializers.EmailField(required=False),
                    "refresh": serializers.CharField(required=False),
                    "access": serializers.CharField(required=False),
                },
            )
        },
        description=(
            "Sem verificação em duas etapas (`otp_ativo` falso, o padrão) devolve "
            "`refresh`/`access`. Com ela ligada, envia o código por e-mail e devolve "
            "`otp_token` para `/api/auth/otp/verify/`."
        ),
    )
    def post(self, request):
        matricula = request.data.get("matricula")
        password = request.data.get("password")

        if not matricula or not password:
            return Response(
                {"detail": "Matrícula e senha são obrigatórias."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = authenticate(
            request,
            matricula=matricula,
            password=password,
        )

        if user is None:
            return Response(
                {"detail": "Credenciais inválidas."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Contas comuns sem verificação em duas etapas entram direto com os tokens.
        # Contas is_staff ou is_superuser têm OTP obrigatório (ignora otp_ativo=False).
        requer_otp = user.otp_ativo or user.is_staff or user.is_superuser
        if not requer_otp:
            refresh = RefreshToken.for_user(user)
            return Response(
                {
                    "otp_required": False,
                    "refresh": str(refresh),
                    "access": str(refresh.access_token),
                },
                status=status.HTTP_200_OK,
            )

        otp_token, code = create_otp(user.pk)

        enviar_email_otp(user, code)

        return Response(
            {
                "otp_required": True,
                "otp_token": otp_token,
                "email": mask_email(user.email),
            },
            status=status.HTTP_200_OK,
        )
