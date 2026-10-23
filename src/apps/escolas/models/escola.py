from django.db import models

from core.models import BaseModel

from .config import Config


class Escola(BaseModel):
    nome = models.CharField(max_length=45)
    endereco = models.CharField(max_length=45, blank=True)
    config = models.ForeignKey(
        Config,
        related_name="escolas",
        on_delete=models.SET_NULL,
        null=True,
    )
