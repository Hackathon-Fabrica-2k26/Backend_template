import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from .factories import UserFactory


@pytest.fixture(autouse=True)
def limpar_cache(settings):
    """Zera o cache (throttle/OTP) entre os testes usando memória local."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    cache.clear()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    return UserFactory(email="ana@example.com", name="Ana")


@pytest.fixture
def auth_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client
