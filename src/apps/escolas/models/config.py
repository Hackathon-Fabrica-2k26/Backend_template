from django.db import models

from core.models import BaseModel

from ..fields import EncryptedCharField


class Config(BaseModel):
    api_key = EncryptedCharField(max_length=512)
    modelo = models.CharField(max_length=45)
    campos_form = models.JSONField(default=dict)

    def __str__(self):
        return self.modelo
