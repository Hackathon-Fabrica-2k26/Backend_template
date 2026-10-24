from django.conf import settings
from django.db import models

from core.models import BaseModel


class Atividade(BaseModel):
    class OrigemChoices(models.TextChoices):
        TEXTO = "texto", "Texto"
        PDF = "pdf", "PDF"
        DOCX = "docx", "DOCX"

    class StatusChoices(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        VARIACOES_GERADAS = "variacoes_geradas", "Variações geradas"
        APROVADA = "aprovada", "Aprovada"
        ENCERRADA = "encerrada", "Encerrada"

    turma = models.ForeignKey(
        "escolas.Turma",
        on_delete=models.CASCADE,
        related_name="atividades",
        verbose_name="turma",
    )
    criada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="atividades_criadas",
        verbose_name="criada por",
    )
    titulo = models.CharField("título", max_length=255)
    origem = models.CharField(
        "origem",
        max_length=10,
        choices=OrigemChoices.choices,
        default=OrigemChoices.TEXTO,
    )
    texto_original = models.TextField("texto original")
    objetivo = models.TextField("objetivo", blank=True, default="")
    status = models.CharField(
        "status",
        max_length=25,
        choices=StatusChoices.choices,
        default=StatusChoices.RASCUNHO,
    )

    class Meta(BaseModel.Meta):
        verbose_name = "atividade"
        verbose_name_plural = "atividades"
        ordering = ["-created_at"]

    def __str__(self):
        return str(self.titulo)
