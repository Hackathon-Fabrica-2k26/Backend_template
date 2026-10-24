from django.core.mail import send_mail
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ..services.otp import resend_otp


class OTPResendView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp_resend"

    @extend_schema(
        request=inline_serializer(
            name="OTPResendRequest",
            fields={"otp_token": serializers.CharField()},
        ),
        responses={204: None},
    )
    def post(self, request):
        otp_token = request.data.get("otp_token")

        if not otp_token:
            return Response(
                {"detail": "otp_token é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        def send_code(user, code):
            send_mail(
                subject="Seu novo código de verificação",
                message=f"Seu código de verificação é: {code}",
                from_email=None,
                recipient_list=[user.email],
                fail_silently=False,
            )

        try:
            success, error = resend_otp(otp_token, send_code)
        except Exception:
            return Response(
                {"detail": "Não foi possível enviar o código por e-mail."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if not success:
            return Response(
                {"detail": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(status=status.HTTP_204_NO_CONTENT)
