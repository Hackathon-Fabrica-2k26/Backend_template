from datetime import date

from django.conf import settings
from django.db import models

from core.models import BaseModel

from .escola import Escola


def ano_letivo_atual() -> int:
    return date.today().year


class Turma(BaseModel):
    class TurnoChoices(models.TextChoices):
        MANHA = "manha", "Manhã"
        TARDE = "tarde", "Tarde"
        NOITE = "noite", "Noite"
        INTEGRAL = "integral", "Integral"

    nome = models.CharField(max_length=45)
    turno = models.CharField(
        "turno",
        max_length=10,
        choices=TurnoChoices.choices,
        default=TurnoChoices.MANHA,
    )
    ano_letivo = models.PositiveSmallIntegerField(
        "ano letivo",
        default=ano_letivo_atual,
    )
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
