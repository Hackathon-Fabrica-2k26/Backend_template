from django.conf import settings
from rest_framework.permissions import BasePermission


class SpectacularDocsPermission(BasePermission):
    """Permite acesso público à documentação em desenvolvimento (DEBUG=True).

    Em produção (DEBUG=False), restringe o acesso ao schema e Swagger para usuários autenticados.
    """

    def has_permission(self, request, view):
        if getattr(settings, "DEBUG", False):
            return True
        return bool(request.user and request.user.is_authenticated)
