from django.db import models

from core.models import BaseModel


class Config(BaseModel):
    api_key = models.CharField(max_length=255)
    modelo = models.CharField(max_length=45)
    campos_form = models.JSONField(default=dict)

    def __str__(self):
        return self.modelo