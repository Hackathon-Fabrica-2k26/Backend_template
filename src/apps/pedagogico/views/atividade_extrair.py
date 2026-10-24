"""Extração de texto e sugestão de título/descrição a partir de arquivo PDF/DOCX."""

from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.escolas.models import Turma
from apps.escolas.services.escola_usuario import config_ia_do_usuario
from apps.pedagogico.services import (
    MODELO_PADRAO,
    ExtracaoError,
    extrair_texto,
    identificar_origem,
    sugerir_atividade,
)


class AtividadeExtrairSerializer(serializers.Serializer):
    """Payload multipart para extração de atividade."""

    arquivo = serializers.FileField()
    turma = serializers.PrimaryKeyRelatedField(
        queryset=Turma.objects.all(),
        required=False,
        allow_null=True,
    )

    def validate_turma(self, turma):
        if turma is None:
            return None
        request = self.context.get("request")
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            if not turma.professores.filter(pk=request.user.pk).exists():
                raise serializers.ValidationError(
                    "Você só pode extrair atividades para as suas turmas."
                )
        return turma


class AtividadeExtrairRespostaSerializer(serializers.Serializer):
    """Resposta da extração de arquivo com sugestão de IA (sem persistência)."""

    titulo = serializers.CharField()
    descricao = serializers.CharField()
    texto_original = serializers.CharField()
    origem = serializers.ChoiceField(choices=["pdf", "docx"])


class AtividadeExtrairView(APIView):
    """Extrai o texto de um PDF ou DOCX em memória e sugere título e descrição com IA."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = AtividadeExtrairSerializer

    @extend_schema(
        request=AtividadeExtrairSerializer,
        responses={200: AtividadeExtrairRespostaSerializer},
    )
    def post(self, request):
        entrada = AtividadeExtrairSerializer(
            data=request.data,
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

        config = config_ia_do_usuario(request.user)
        sugestao = sugerir_atividade(
            texto_original=texto_original,
            api_key=config.api_key if config else "",
            nome_arquivo=getattr(arquivo, "name", "") or "",
            modelo=config.modelo if config and config.modelo else MODELO_PADRAO,
        )

        return Response(
            {
                "titulo": sugestao["titulo"],
                "descricao": sugestao["descricao"],
                "texto_original": texto_original,
                "origem": origem,
            },
            status=status.HTTP_200_OK,
        )
