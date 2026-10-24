"""Endpoint para reconhecer nomes de alunos em foto de lista de chamada (OCR)."""

from pathlib import Path

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.escolas.services import LLMError, reconhecer_nomes

TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB

MIMES_PERMITIDOS = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
}

EXTENSOES_PARA_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class ChamadaReconhecerSerializer(serializers.Serializer):
    """Valida o arquivo de imagem enviado no multipart/form-data."""

    imagem = serializers.FileField(required=True)

    def validate_imagem(self, arquivo):
        if arquivo.size <= 0:
            raise serializers.ValidationError("O arquivo enviado está vazio.")
        if arquivo.size > TAMANHO_MAXIMO_BYTES:
            raise serializers.ValidationError("A imagem deve ter no máximo 10 MB.")

        content_type = (getattr(arquivo, "content_type", "") or "").lower().strip()
        extensao = Path(getattr(arquivo, "name", "") or "").suffix.lower()

        mime = MIMES_PERMITIDOS.get(content_type)
        if mime is None and content_type in ("", "application/octet-stream"):
            mime = EXTENSOES_PARA_MIME.get(extensao)
        if mime is None or (extensao and extensao not in EXTENSOES_PARA_MIME):
            raise serializers.ValidationError(
                "Formato inválido. Envie uma imagem JPG, PNG ou WEBP."
            )

        self.context["mime"] = mime
        return arquivo


class ChamadaReconhecerRespostaSerializer(serializers.Serializer):
    """Lista de nomes reconhecidos na imagem da chamada."""

    nomes = serializers.ListField(child=serializers.CharField())


class ChamadaReconhecerView(APIView):
    """Reconhece os nomes dos alunos a partir da foto da chamada sem gravar a imagem."""

    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=ChamadaReconhecerSerializer,
        responses={
            200: ChamadaReconhecerRespostaSerializer,
            400: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
    )
    def post(self, request):
        contexto: dict = {}
        entrada = ChamadaReconhecerSerializer(data=request.data, context=contexto)
        entrada.is_valid(raise_exception=True)

        arquivo = entrada.validated_data["imagem"]
        imagem_bytes = arquivo.read()
        mime = contexto["mime"]

        config = request.user.escola.config if getattr(request.user, "escola", None) else None
        try:
            nomes = reconhecer_nomes(imagem_bytes, mime, config)
        except LLMError as erro:
            return Response({"erro": str(erro)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response({"nomes": nomes}, status=status.HTTP_200_OK)
