from django.db import models

from core.models import BaseModel


class Relatorio(BaseModel):
    dados = models.JSONField("dados", default=dict)
    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="relatorios",
        verbose_name="aluno",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "relatório"
        verbose_name_plural = "relatórios"

    def __str__(self):
        return f"Relatório #{self.pk} (Aluno {self.aluno_id})"
