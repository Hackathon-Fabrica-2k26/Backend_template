from django.db import models

from apps.escolas.utils.crypto import decrypt_value, encrypt_value


class EncryptedCharField(models.CharField):
    """CharField que armazena os dados cifrados com Fernet no banco e os decifra na leitura."""

    description = "String cifrada com Fernet no banco de dados"

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 512)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if not value:
            return ""
        return decrypt_value(value)

    def to_python(self, value):
        if isinstance(value, str):
            return decrypt_value(value)
        return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value:
            return ""
        return encrypt_value(value)
