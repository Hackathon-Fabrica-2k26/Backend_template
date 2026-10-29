from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken


class LogoutView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(
        summary="Logout e invalidação do refresh token",
        description=(
            "Coloca o refresh token na blacklist, impedindo sua reutilização "
            "e a geração de novos tokens de acesso."
        ),
        request=inline_serializer(
            name="LogoutRequest",
            fields={
                "refresh": serializers.CharField(
                    required=True,
                    help_text="Refresh token a ser invalidado (colocado na blacklist).",
                ),
            },
        ),
        responses={
            200: inline_serializer(
                name="LogoutResponse",
                fields={
                    "mensagem": serializers.CharField(),
                },
            ),
            400: inline_serializer(
                name="LogoutErrorResponse",
                fields={
                    "erro": serializers.CharField(),
                },
            ),
        },
    )
    def post(self, request):
        refresh = request.data.get("refresh")
        if not refresh:
            return Response(
                {"erro": "O campo 'refresh' é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            token = RefreshToken(refresh)
            token.blacklist()
            return Response(
                {"mensagem": "Logout realizado com sucesso."},
                status=status.HTTP_200_OK,
            )
        except TokenError as e:
            return Response(
                {"erro": str(e) or "Token inválido ou expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
