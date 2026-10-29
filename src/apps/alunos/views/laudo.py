"""Endpoint POST /api/alunos/{id}/laudo/ para converter laudo em PerfilApoio (B#44)."""

from pathlib import Path

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alunos.models import Aluno
from apps.alunos.services import (
    DocumentoRecusadoError,
    NomeNaoConfereError,
    processar_laudo,
    tem_consentimento_ativo,
)
from apps.alunos.services.laudo import MIMES_LAUDO_PERMITIDOS, TAMANHO_MAXIMO_LAUDO_BYTES
from apps.escolas.services.escola_usuario import config_ia_do_usuario
from apps.pedagogico.serializers import PerfilApoioSerializer
from apps.pedagogico.services import LLMError

EXTENSOES_PARA_MIME = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
}


class AlunoLaudoUploadSerializer(serializers.Serializer):
    """Valida o arquivo do laudo (PDF, JPG, PNG ou WEBP até 10 MB)."""

    arquivo = serializers.FileField(required=True)
    confirmar_nome = serializers.BooleanField(required=False, default=False)

    def validate_arquivo(self, arquivo):
        if arquivo.size <= 0:
            raise serializers.ValidationError("O arquivo enviado está vazio.")
        if arquivo.size > TAMANHO_MAXIMO_LAUDO_BYTES:
            raise serializers.ValidationError("O arquivo deve ter no máximo 10 MB.")

        content_type = (getattr(arquivo, "content_type", "") or "").lower().strip()
        extensao = Path(getattr(arquivo, "name", "") or "").suffix.lower()

        mime = MIMES_LAUDO_PERMITIDOS.get(content_type)
        if mime is None and content_type in ("", "application/octet-stream"):
            mime = EXTENSOES_PARA_MIME.get(extensao)
        if mime is None or (extensao and extensao not in EXTENSOES_PARA_MIME):
            raise serializers.ValidationError(
                "Formato inválido. Envie um arquivo PDF, JPG, PNG ou WEBP."
            )

        self.context["mime"] = mime
        return arquivo


class AlunoLaudoRespostaSerializer(serializers.Serializer):
    """Resposta do processamento do laudo em memória."""

    perfil_apoio = PerfilApoioSerializer()
    nome_conferiu = serializers.BooleanField()
    arquivo_excluido_em = serializers.CharField()


def _obter_aluno_do_professor(user, aluno_id: int) -> Aluno | None:
    """Retorna o aluno se pertencer a uma turma do professor autenticado."""
    return (
        Aluno.objects.select_related(
            "turma",
            "turma__escola",
            "turma__escola__config",
        )
        .filter(
            pk=aluno_id,
            turma__professores=user,
            deleted__isnull=True,
        )
        .first()
    )


class AlunoLaudoView(APIView):
    """Processa o laudo em memória via Gemini, cria/atualiza o PerfilApoio e descarta o arquivo."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = AlunoLaudoUploadSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                type=OpenApiTypes.INT,
                location=OpenApiParameter.PATH,
                description="ID do aluno.",
            )
        ],
        request=AlunoLaudoUploadSerializer,
        responses={
            200: AlunoLaudoRespostaSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
            404: OpenApiTypes.OBJECT,
            409: OpenApiTypes.OBJECT,
            422: OpenApiTypes.OBJECT,
            502: OpenApiTypes.OBJECT,
        },
        description=(
            "Envia o laudo (PDF, JPG, PNG ou WEBP até 10 MB) em memória ao Gemini para "
            "extrair necessidades pedagógicas e estratégias de apoio sem diagnóstico, CID "
            "ou médico, confere o nome com o aluno, atualiza o PerfilApoio ativo e descarta "
            "imediatamente o arquivo."
        ),
    )
    def post(self, request, id: int):
        aluno = _obter_aluno_do_professor(request.user, id)
        if aluno is None:
            return Response(
                {"detail": "Não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not tem_consentimento_ativo(aluno):
            return Response(
                {"erro": "Aluno sem consentimento ativo do responsável para uso de IA."},
                status=status.HTTP_403_FORBIDDEN,
            )

        escola = aluno.turma.escola if aluno.turma else None
        config = config_ia_do_usuario(request.user, escola=escola)
        return processar_upload_laudo(request, aluno, config)


def processar_upload_laudo(request, aluno: Aluno, config) -> Response:
    """Valida o arquivo e processa o laudo em memória (professora ou responsável)."""
    contexto: dict = {}
    entrada = AlunoLaudoUploadSerializer(data=request.data, context=contexto)
    entrada.is_valid(raise_exception=True)

    arquivo = entrada.validated_data["arquivo"]
    confirmar_nome = bool(
        entrada.validated_data.get("confirmar_nome")
        or str(request.query_params.get("confirmar_nome", "")).lower() in ("true", "1")
        or str(request.data.get("confirmar_nome", "")).lower() in ("true", "1")
    )
    try:
        arquivo_bytes = arquivo.read()
    finally:
        arquivo.close()

    try:
        resultado = processar_laudo(
            aluno=aluno,
            arquivo_bytes=arquivo_bytes,
            mime=contexto["mime"],
            config=config,
            confirmar_nome=confirmar_nome,
        )
    except DocumentoRecusadoError as erro:
        return Response(
            {
                "erro": str(erro),
                "tipo_documento": erro.tipo_documento,
                "motivo": erro.motivo,
            },
            status=status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    except NomeNaoConfereError as erro:
        return Response(
            {
                "erro": str(erro),
                "confirmacao_necessaria": True,
            },
            status=status.HTTP_409_CONFLICT,
        )
    except LLMError as erro:
        return Response({"erro": str(erro)}, status=status.HTTP_502_BAD_GATEWAY)

    return Response(resultado, status=status.HTTP_200_OK)
