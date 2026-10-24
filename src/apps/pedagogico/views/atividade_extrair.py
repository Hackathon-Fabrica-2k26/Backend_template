
from drf_spectacular.utils import OpenApiRequest, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.escolas.models import Turma
from apps.pedagogico.services import (
    MODELO_PADRAO,
    ExtracaoError,
    LLMError,
    extrair_atividade_multimodal,
    extrair_texto,
    identificar_origem,
    sugerir_atividade,
)


class AtividadeExtrairSerializer(serializers.Serializer):
    """Payload multipart para extração de atividade."""

    arquivo = serializers.FileField(
        help_text="Arquivo PDF, DOCX, JPG, PNG ou WEBP (máximo de 20 MB)."
    )
    turma = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_turma(self, turma):
        if turma is None:
            return None

        request = self.context.get("request")

        if (
            getattr(request, "user", None) is not None
            and request.user.is_authenticated
        ):
            if not turma.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode extrair atividades para as suas turmas."
                )

        return turma


class AtividadeExtrairUploadSerializer(serializers.Serializer):
    """Schema específico para documentar o upload binário."""

    arquivo = serializers.FileField()
    turma = serializers.IntegerField(required=False, allow_null=True)


class AtividadeExtrairRespostaSerializer(serializers.Serializer):
    """Resposta da extração de arquivo com sugestão de IA."""

    titulo = serializers.CharField()
    descricao = serializers.CharField()
    texto_original = serializers.CharField()
    origem = serializers.ChoiceField(
        choices=["pdf", "docx", "jpg", "png", "webp"]
    )


class AtividadeExtrairView(APIView):
    """Extrai arquivos em memória e sugere dados para a atividade."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = AtividadeExtrairSerializer

    @extend_schema(
        request=OpenApiRequest(
            request=AtividadeExtrairUploadSerializer,
            encoding={"arquivo": {"contentType": "application/octet-stream"}},
        ),
        responses={200: AtividadeExtrairRespostaSerializer},
    )
    def post(self, request):
        # Processa o multipart para que o upload handler detecte
        # se o arquivo ultrapassou o limite permitido.
        dados_entrada = request.data

        if getattr(request._request, "upload_excedeu_limite", False):
            return Response(
                {
                    "arquivo": [
                        "O arquivo excede o limite máximo de 20 MB."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        entrada = AtividadeExtrairSerializer(
            data=dados_entrada,
            context={"request": request},
        )
        entrada.is_valid(raise_exception=True)
        arquivo = entrada.validated_data["arquivo"]

        try:
            origem = identificar_origem(arquivo)
            texto_original = extrair_texto(arquivo)
        except ExtracaoError as erro:
            return Response(
                {"arquivo": [str(erro)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        escola = getattr(request.user, "escola", None)
        config = getattr(escola, "config", None) if escola else None

        api_key = config.api_key if config else ""
        modelo = (
            config.modelo
            if config and config.modelo
            else MODELO_PADRAO
        )

        precisa_multimodal = origem in {"jpg", "png", "webp"} or (
            origem == "pdf" and not texto_original.strip()
        )

        try:
            if precisa_multimodal:
                arquivo.seek(0)
                conteudo_bytes = arquivo.read()

                mime_types = {
                    "pdf": "application/pdf",
                    "jpg": "image/jpeg",
                    "png": "image/png",
                    "webp": "image/webp",
                }

                dados = extrair_atividade_multimodal(
                    conteudo_bytes=conteudo_bytes,
                    mime_type=mime_types[origem],
                    api_key=api_key,
                    modelo=modelo,
                )

                texto_original = dados["texto_original"]
            else:
                dados = sugerir_atividade(
                    texto_original=texto_original,
                    api_key=api_key,
                    nome_arquivo=getattr(arquivo, "name", "") or "",
                    modelo=modelo,
                )

        except LLMError as erro:
            return Response(
                {"detail": str(erro)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        except ExtracaoError as erro:
            return Response(
                {"arquivo": [str(erro)]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        resposta = {
            "titulo": dados["titulo"],
            "descricao": dados["descricao"],
            "texto_original": texto_original,
            "origem": origem,
        }

        return Response(resposta, status=status.HTTP_200_OK)
