from drf_spectacular.extensions import OpenApiAuthenticationExtension
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import BasePermission

from apps.alunos.services import SessaoResponsavel, validar_token

PREFIXO = b"responsavel"


class ResponsavelPrincipal:
    """Identidade do responsável sem conta, limitada ao aluno do código usado."""

    is_authenticated = True
    is_anonymous = False

    def __init__(self, sessao: SessaoResponsavel):
        self.responsavel = sessao.responsavel
        self.aluno = sessao.aluno
        self.pk = sessao.responsavel.pk

    def __str__(self):
        return f"Responsável #{self.pk}"


class ResponsavelAuthentication(BaseAuthentication):
    """Header `Authorization: Responsavel <token>` (token assinado, 24h)."""

    def authenticate(self, request):
        partes = get_authorization_header(request).split()
        if not partes or partes[0].lower() != PREFIXO:
            return None
        if len(partes) != 2:
            raise AuthenticationFailed("Token inválido.")
        sessao = validar_token(partes[1].decode(errors="ignore"))
        if sessao is None:
            raise AuthenticationFailed("Token inválido ou expirado.")
        return ResponsavelPrincipal(sessao), None

    def authenticate_header(self, request):
        return "Responsavel"


class IsResponsavel(BasePermission):
    def has_permission(self, request, view):
        return isinstance(request.user, ResponsavelPrincipal)


class ResponsavelAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "apps.alunos.authentication.ResponsavelAuthentication"
    name = "responsavelAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": "Formato: `Responsavel <token>` (token de 24h).",
        }