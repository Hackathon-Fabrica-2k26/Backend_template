from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.alunos.authentication import IsResponsavel, ResponsavelAuthentication
from apps.alunos.models import Consentimento
from apps.alunos.models.consentimento import FINALIDADE_PADRAO
from apps.alunos.serializers.codigo_acesso import (
    ResponsavelAcessoSerializer,
    ResponsavelAlunoSerializer,
    ResponsavelConsentimentoSerializer,
    ResponsavelTokenSerializer,
)
from apps.alunos.services import (
    CodigoInvalido,
    emitir_token,
    revogar_consentimento,
    tem_consentimento_ativo,
    vincular_responsavel,
)
from apps.alunos.services.codigo_acesso import VALIDADE_TOKEN_SEGUNDOS
from apps.alunos.views.laudo import (
    AlunoLaudoRespostaSerializer,
    AlunoLaudoUploadSerializer,
    processar_upload_laudo,
)
from apps.escolas.services.escola_usuario import config_ia_do_usuario
from apps.pedagogico.models import PerfilApoio
from apps.pedagogico.serializers import PerfilApoioSerializer


class ResponsavelAcessoView(APIView):
    """Troca o código do aluno por um token de 24h (sem conta). Limitado por IP."""

    authentication_classes: list = []
    permission_classes = [AllowAny]
    throttle_scope = "codigo_acesso"
    serializer_class = ResponsavelAcessoSerializer

    @extend_schema(
        request=ResponsavelAcessoSerializer,
        responses={
            200: ResponsavelTokenSerializer,
            400: OpenApiResponse(description="Código inválido, expirado, usado ou revogado."),
            429: OpenApiResponse(description="Muitas tentativas."),
        },
    )
    def post(self, request):
        serializer = ResponsavelAcessoSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dados = serializer.validated_data
        try:
            responsavel, aluno = vincular_responsavel(
                dados["codigo"],
                dados["nome"],
                dados.get("email", ""),
                dados.get("parentesco", ""),
            )
        except CodigoInvalido:
            return Response(
                {"erro": "Código inválido ou expirado."}, status=status.HTTP_400_BAD_REQUEST
            )
        return Response(
            {
                "token": emitir_token(responsavel, aluno),
                "tipo": "Responsavel",
                "expira_em_segundos": VALIDADE_TOKEN_SEGUNDOS,
            }
        )


class _ResponsavelBase(APIView):
    authentication_classes = [ResponsavelAuthentication]
    permission_classes = [IsResponsavel]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        # O histórico (simple_history) lê request.user como FK de usuário; o responsável não é um.
        request._request.user = AnonymousUser()


def _estado_consentimento(aluno) -> dict:
    ativo = (
        Consentimento.objects.filter(
            aluno=aluno, finalidade=FINALIDADE_PADRAO, revogado_em__isnull=True
        )
        .order_by("-aceito_em")
        .first()
    )
    if ativo is not None:
        return {"consentimento_ativo": True, "aceito_em": ativo.aceito_em, "revogado_em": None}
    ultimo = (
        Consentimento.objects.filter(aluno=aluno, finalidade=FINALIDADE_PADRAO)
        .order_by("-aceito_em")
        .first()
    )
    return {
        "consentimento_ativo": False,
        "aceito_em": ultimo.aceito_em if ultimo else None,
        "revogado_em": ultimo.revogado_em if ultimo else None,
    }


class ResponsavelAlunoView(_ResponsavelBase):
    """Dados mínimos do aluno do responsável: nome, turma e se há consentimento."""

    serializer_class = ResponsavelAlunoSerializer

    @extend_schema(responses=ResponsavelAlunoSerializer)
    def get(self, request):
        aluno = request.user.aluno
        return Response(
            {
                "nome": aluno.nome,
                "turma": aluno.turma.nome if aluno.turma else None,
                "consentimento_ativo": tem_consentimento_ativo(aluno),
            }
        )


class ResponsavelConsentimentoView(_ResponsavelBase):
    """Registra o consentimento do responsável para o aluno do seu token."""

    serializer_class = ResponsavelConsentimentoSerializer

    @extend_schema(
        request=None,
        responses={
            201: ResponsavelConsentimentoSerializer,
            400: OpenApiResponse(description="Já existe consentimento ativo."),
        },
    )
    def post(self, request):
        aluno = request.user.aluno
        if tem_consentimento_ativo(aluno):
            return Response(
                {"erro": "Já existe consentimento ativo para este aluno."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        Consentimento.objects.create(
            aluno=aluno, responsavel=request.user.responsavel, aceito_em=timezone.now()
        )
        return Response(_estado_consentimento(aluno), status=status.HTTP_201_CREATED)


class ResponsavelConsentimentoRevogarView(_ResponsavelBase):
    """Revoga o consentimento ativo e apaga os dados derivados da IA."""

    serializer_class = ResponsavelConsentimentoSerializer

    @extend_schema(
        request=None,
        responses={
            200: ResponsavelConsentimentoSerializer,
            400: OpenApiResponse(description="Não há consentimento ativo."),
        },
    )
    def post(self, request):
        aluno = request.user.aluno
        consentimento = Consentimento.objects.filter(
            aluno=aluno, finalidade=FINALIDADE_PADRAO, revogado_em__isnull=True
        ).first()
        if consentimento is None:
            return Response(
                {"erro": "Não há consentimento ativo para este aluno."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        revogar_consentimento(consentimento)
        return Response(_estado_consentimento(aluno))


class ResponsavelLaudoView(_ResponsavelBase):
    """O responsável envia o laudo do aluno do seu token; mesmo processamento da professora."""

    parser_classes = [MultiPartParser, FormParser]
    serializer_class = AlunoLaudoUploadSerializer

    @extend_schema(
        request=AlunoLaudoUploadSerializer,
        responses={
            200: AlunoLaudoRespostaSerializer,
            400: OpenApiResponse(description="Arquivo inválido."),
            403: OpenApiResponse(description="Sem consentimento ativo."),
            409: OpenApiResponse(
                description="Nome no laudo diferente do aluno; exige confirmação."
            ),
            422: OpenApiResponse(description="Documento recusado (fora de contexto)."),
            502: OpenApiResponse(description="Falha na IA."),
        },
    )
    def post(self, request):
        aluno = request.user.aluno
        if not tem_consentimento_ativo(aluno):
            return Response(
                {"erro": "Registre o consentimento antes de enviar o laudo."},
                status=status.HTTP_403_FORBIDDEN,
            )
        escola = aluno.turma.escola if aluno.turma else None
        return processar_upload_laudo(request, aluno, config_ia_do_usuario(None, escola=escola))


class ResponsavelPerfilApoioEdicaoSerializer(serializers.Serializer):
    necessidades = serializers.ListField(
        child=serializers.CharField(max_length=500), required=False
    )
    estrategias = serializers.ListField(child=serializers.CharField(max_length=500), required=False)
    observacoes = serializers.CharField(required=False, allow_blank=True)


class ResponsavelPerfilApoioView(_ResponsavelBase):
    """Perfil de apoio ativo do aluno do token, para o responsável conferir e corrigir."""

    serializer_class = PerfilApoioSerializer

    def _perfil(self, request):
        return (
            PerfilApoio.objects.filter(aluno=request.user.aluno, ativo=True)
            .order_by("-created_at")
            .first()
        )

    @extend_schema(responses={200: PerfilApoioSerializer, 404: OpenApiResponse()})
    def get(self, request):
        perfil = self._perfil(request)
        if perfil is None:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        return Response(PerfilApoioSerializer(perfil).data)

    @extend_schema(
        request=ResponsavelPerfilApoioEdicaoSerializer,
        responses={200: PerfilApoioSerializer, 404: OpenApiResponse()},
    )
    def patch(self, request):
        perfil = self._perfil(request)
        if perfil is None:
            return Response({"detail": "Não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        entrada = ResponsavelPerfilApoioEdicaoSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        for campo, valor in entrada.validated_data.items():
            setattr(perfil, campo, valor)
        perfil.save()
        return Response(PerfilApoioSerializer(perfil).data)
