import pytest
from rest_framework.test import APIRequestFactory

from core.authentication import DevAuthentication

pytestmark = pytest.mark.django_db


def test_cria_e_reutiliza_usuario_de_desenvolvimento():
    request = APIRequestFactory().get("/")
    usuario, _ = DevAuthentication().authenticate(request)
    outro, _ = DevAuthentication().authenticate(request)
    assert usuario.pk == outro.pk
    assert usuario.email == "dev@example.com"
    assert usuario.is_superuser is False
