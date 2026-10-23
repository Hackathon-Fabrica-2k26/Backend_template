from django.contrib.auth import get_user_model
from rest_framework.authentication import BaseAuthentication


class DevAuthentication(BaseAuthentication):
    """Autentica toda requisição sem token como um usuário de desenvolvimento.

    Só é ativada com AUTH_DISABLED=True (e DEBUG=True). Um token válido continua tendo
    prioridade, porque o JWT vem antes na lista de autenticadores.
    """

    EMAIL = "dev@example.com"

    def authenticate(self, request):
        User = get_user_model()
        usuario, _ = User.objects.get_or_create(
            email=self.EMAIL,
            defaults={"name": "Dev", "matricula": "dev"},
        )
        return usuario, None
