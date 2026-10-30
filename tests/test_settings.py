import importlib

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def recarregar(monkeypatch, **env):
    import config.settings as cfg

    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)
    for chave in (
        "DEBUG",
        "SECRET_KEY",
        "DATABASE_URL",
        "REDIS_URL",
        "CSRF_TRUSTED_ORIGINS",
        "CONFIG_FERNET_KEY",
    ):
        monkeypatch.delenv(chave, raising=False)
    env_com_padrao = {"CONFIG_FERNET_KEY": "chave-fernet-para-testes", **env}
    for chave, valor in env_com_padrao.items():
        if valor is None:
            monkeypatch.delenv(chave, raising=False)
        else:
            monkeypatch.setenv(chave, str(valor))
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


def test_producao_sem_config_fernet_key_falha(monkeypatch):
    with pytest.raises(ImproperlyConfigured) as exc_info:
        recarregar(monkeypatch, SECRET_KEY="x", DEBUG="False", CONFIG_FERNET_KEY="")
    assert "CONFIG_FERNET_KEY" in str(exc_info.value)


def test_debug_padrao_e_falso(monkeypatch):
    cfg = recarregar(monkeypatch, SECRET_KEY="x", CONFIG_FERNET_KEY="chave-fernet")
    assert cfg.DEBUG is False


def test_proxy_https_e_csrf_origins(monkeypatch):
    cfg = recarregar(
        monkeypatch,
        SECRET_KEY="x",
        CONFIG_FERNET_KEY="chave-fernet",
        CSRF_TRUSTED_ORIGINS="https://app.exemplo.com,https://b.com",
    )
    assert cfg.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
    assert cfg.CSRF_TRUSTED_ORIGINS == ["https://app.exemplo.com", "https://b.com"]


def test_tempo_de_vida_dos_tokens():
    from datetime import timedelta

    assert settings.SIMPLE_JWT["ACCESS_TOKEN_LIFETIME"] == timedelta(days=2)
    assert settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"] == timedelta(days=7)


def test_auth_desativada_exige_debug(monkeypatch):
    with pytest.raises(ImproperlyConfigured):
        recarregar(monkeypatch, SECRET_KEY="x", DEBUG="False", AUTH_DISABLED="True")


def test_auth_desativada_adiciona_usuario_de_desenvolvimento(monkeypatch):
    cfg = recarregar(monkeypatch, SECRET_KEY="x", DEBUG="True", AUTH_DISABLED="True")
    classes = cfg.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    assert classes[-1] == "core.authentication.DevAuthentication"


def test_auth_ativada_por_padrao(monkeypatch):
    cfg = recarregar(monkeypatch, SECRET_KEY="x", DEBUG="True")
    assert (
        "core.authentication.DevAuthentication"
        not in cfg.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    )


def test_cache_usa_banco_sem_redis(monkeypatch):
    cfg = recarregar(monkeypatch, SECRET_KEY="x")
    assert cfg.CACHES["default"] == {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }


def test_cache_usa_memoria_em_desenvolvimento(monkeypatch):
    cfg = recarregar(monkeypatch, SECRET_KEY="x", DEBUG="True")
    assert cfg.CACHES["default"] == {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }


def test_cache_usa_redis_quando_configurado(monkeypatch):
    cfg = recarregar(monkeypatch, SECRET_KEY="x", REDIS_URL="redis://localhost:6379/0")
    assert cfg.CACHES["default"] == {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": "redis://localhost:6379/0",
    }
