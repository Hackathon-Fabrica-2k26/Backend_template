from django.contrib.auth import authenticate
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.otp import create_otp


def mask_email(email):
    local, domain = email.split("@", 1)
    return f"{local[0]}***@{domain}"


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "login"

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

        otp_token, code = create_otp(user.pk)

        send_mail(
            subject="Seu código de verificação",
            message=f"Seu código de verificação é: {code}",
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )

        return Response(
            {
                "otp_token": otp_token,
                "email": mask_email(user.email),
            },
            status=status.HTTP_200_OK,
        )