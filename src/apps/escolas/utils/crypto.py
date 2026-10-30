import base64
import hashlib
import logging
import os

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

logger = logging.getLogger(__name__)


def get_fernet_key() -> bytes:
    """Retorna a chave Fernet configurada em CONFIG_FERNET_KEY ou derivada do SECRET_KEY."""
    key = getattr(settings, "CONFIG_FERNET_KEY", None) or os.getenv("CONFIG_FERNET_KEY", "")
    if not key:
        secret = getattr(settings, "SECRET_KEY", "dev-insecure-key")
        return base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    if isinstance(key, str):
        return key.strip().encode()
    return key


def get_fernet() -> Fernet:
    """Retorna uma instância de Fernet inicializada com a chave ativa."""
    return Fernet(get_fernet_key())


def is_encrypted(value: str) -> bool:
    """Verifica se a string informada é um token Fernet válido decifrável pela chave ativa."""
    if not value or not isinstance(value, str):
        return False
    if not value.startswith("gAAAAA"):
        return False
    try:
        get_fernet().decrypt(value.encode())
        return True
    except (InvalidToken, Exception):
        return False


def encrypt_value(value: str) -> str:
    """Cifra o texto em claro usando Fernet.

    Se o valor já estiver cifrado ou for vazio, retorna-o inalterado.
    """
    if not value or not isinstance(value, str):
        return value or ""
    if is_encrypted(value):
        return value
    return get_fernet().encrypt(value.encode()).decode()


def decrypt_value(value: str) -> str:
    """Decifra o valor cifrado com Fernet.

    Se o valor não for um token cifrado válido (ex: dado legado em texto puro),
    retorna o valor original para garantir compatibilidade retroativa e resiliência.
    """
    if not value or not isinstance(value, str):
        return value or ""
    try:
        return get_fernet().decrypt(value.encode()).decode()
    except (InvalidToken, Exception):
        if value.startswith("gAAAAA"):
            logger.error("Config.api_key: falha ao decifrar (chave Fernet trocada?)")
        return value
