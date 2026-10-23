
from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from ..models import User
from ..services.otp import verify_otp


class OTPVerifyView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "otp_verify"

    @extend_schema(
        request=inline_serializer(
            name="OTPVerifyRequest",
            fields={
                "otp_token": serializers.CharField(),
                "code": serializers.CharField(),
            },
        ),
        responses={
            200: inline_serializer(
                name="OTPVerifyResponse",
                fields={
                    "refresh": serializers.CharField(),
                    "access": serializers.CharField(),
                },
            )
        },
    )
    def post(self, request):
        otp_token = request.data.get("otp_token")
        code = request.data.get("code")

        if not otp_token or code is None:
            return Response(
                {"detail": "otp_token e code são obrigatórios."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid, user_id, error = verify_otp(otp_token, code)

        if not valid:
            return Response(
                {"detail": error},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return Response(
                {"detail": "Usuário inválido ou inativo."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
            status=status.HTTP_200_OK,
        )
