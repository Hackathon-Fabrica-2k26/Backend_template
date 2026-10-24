"""Endpoint para reconhecer nomes de alunos em foto ou PDF de lista de chamada (OCR)."""

from pathlib import Path

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.escolas.services import LLMError, reconhecer_nomes
from apps.escolas.services.escola_usuario import config_ia_do_usuario

TAMANHO_MAXIMO_BYTES = 10 * 1024 * 1024  # 10 MB

MIMES_PERMITIDOS = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "application/pdf": "application/pdf",
}

EXTENSOES_PARA_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


class ChamadaReconhecerSerializer(serializers.Serializer):
    """Valida o arquivo (imagem ou PDF) enviado no multipart/form-data."""

    imagem = serializers.FileField(required=True)

    def validate_imagem(self, arquivo):
        if arquivo.size <= 0:
            raise serializers.ValidationError("O arquivo enviado está vazio.")
        if arquivo.size > TAMANHO_MAXIMO_BYTES:
            raise serializers.ValidationError("O arquivo deve ter no máximo 10 MB.")

        content_type = (getattr(arquivo, "content_type", "") or "").lower().strip()
        extensao = Path(getattr(arquivo, "name", "") or "").suffix.lower()

        mime = MIMES_PERMITIDOS.get(content_type)
        if mime is None and content_type in ("", "application/octet-stream"):
            mime = EXTENSOES_PARA_MIME.get(extensao)
        if mime is None or (extensao and extensao not in EXTENSOES_PARA_MIME):
            raise serializers.ValidationError(
                "Formato inválido. Envie um arquivo PDF, JPG, PNG ou WEBP."
            )

        self.context["mime"] = mime
        return arquivo


class ChamadaNomeItemSerializer(serializers.Serializer):
    """Item reconhecido na chamada com nome e índice de confiança."""

    nome = serializers.CharField()
    confianca = serializers.FloatField(min_value=0.0, max_value=1.0)


class ChamadaReconhecerRespostaSerializer(serializers.Serializer):
    """Lista de nomes reconhecidos na chamada (com confiança e lista de texto)."""

    nomes = ChamadaNomeItemSerializer(many=True)
    nomes_texto = serializers.ListField(child=serializers.CharField())


class ChamadaReconhecerView(APIView):
    """Reconhece os nomes dos alunos a partir da foto ou PDF da chamada sem gravar o arquivo."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = ChamadaReconhecerSerializer

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

        config = config_ia_do_usuario(request.user)
        try:
            nomes = reconhecer_nomes(imagem_bytes, mime, config)
        except LLMError as erro:
            return Response({"erro": str(erro)}, status=status.HTTP_502_BAD_GATEWAY)

        nomes_texto = [str(item["nome"]) for item in nomes]
        return Response(
            {
                "nomes": nomes,
                "nomes_texto": nomes_texto,
            },
            status=status.HTTP_200_OK,
        )
