from django.conf import settings
from django.db import models

from core.models import BaseModel


class EnvioTrabalhos(BaseModel):
    """Registro de lote de envio de trabalhos de uma atividade."""

    class StatusChoices(models.TextChoices):
        PROCESSANDO = "processando", "Processando"
        REVISAO_PENDENTE = "revisao_pendente", "Revisão pendente"
        CONCLUIDO = "concluido", "Concluído"

    atividade = models.ForeignKey(
        "Atividade",
        on_delete=models.CASCADE,
        related_name="envios",
        verbose_name="atividade",
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="envios_trabalhos",
        verbose_name="enviado por",
    )
    total_arquivos = models.PositiveIntegerField("total de arquivos", default=0)
    status = models.CharField(
        "status",
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.PROCESSANDO,
    )

    class Meta(BaseModel.Meta):
        verbose_name = "envio de trabalhos"
        verbose_name_plural = "envios de trabalhos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Envio #{self.pk} - Atividade {self.atividade_id} ({self.status})"
