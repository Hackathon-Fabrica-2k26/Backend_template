import importlib

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def recarregar(monkeypatch, **env):
    import config.settings as cfg

    for chave in ("DEBUG", "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "CSRF_TRUSTED_ORIGINS"):
        monkeypatch.delenv(chave, raising=False)
    for chave, valor in env.items():
        monkeypatch.setenv(chave, valor)
    return importlib.reload(cfg)


@pytest.fixture(autouse=True)
def restaurar_settings(monkeypatch):
    yield
    monkeypatch.undo()
    import config.settings as cfg

    importlib.reload(cfg)


def test_sqlite_por_padrao():
    assert settings.DATABASES["default"]["ENGINE"].endswith("sqlite3")


def test_celery_eager_sem_redis():
    assert settings.CELERY_TASK_ALWAYS_EAGER is True


def test_database_url_vazia_usa_sqlite(monkeypatch):
    cfg = recarregar(monkeypatch, DATABASE_URL="", SECRET_KEY="x")
    assert cfg.DATABASES["default"]["ENGINE"].endswith("sqlite3")


def test_producao_sem_secret_key_falha(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        recarregar(monkeypatch, DEBUG="False")


def test_debug_padrao_e_falso(monkeypatch):
    cfg = recarregar(monkeypatch, SECRET_KEY="x")
    assert cfg.DEBUG is False


def test_proxy_https_e_csrf_origins(monkeypatch):
    cfg = recarregar(
        monkeypatch, SECRET_KEY="x", CSRF_TRUSTED_ORIGINS="https://app.exemplo.com,https://b.com"
    )
    assert cfg.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert cfg.CSRF_TRUSTED_ORIGINS == ["https://app.exemplo.com", "https://b.com"]


def test_tempo_de_vida_dos_tokens():
    from datetime import timedelta

    assert settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] == timedelta(days=2)
    assert settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] == timedelta(days=7)
