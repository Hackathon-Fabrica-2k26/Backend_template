from django.conf import settings
from django.db import models

from core.models import BaseModel

from .escola import Escola


class Turma(BaseModel):
    nome = models.CharField(max_length=45)
    escola = models.ForeignKey(
        Escola,
        on_delete=models.CASCADE,
        related_name="turmas",
    )
    professores = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="turmas",
        blank=True,
    )
