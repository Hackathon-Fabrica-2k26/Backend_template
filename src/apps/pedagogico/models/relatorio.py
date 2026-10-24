from django.db import models

from core.models import BaseModel


class Relatorio(BaseModel):
    TIPOS_RELATORIO = [
        ("atividade", "Atividade"),
        ("geral", "Geral"),
        ("periodo", "Período"),
    ]
    dados = models.JSONField("dados", default=dict)
    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="relatorios",
        verbose_name="aluno",
    )
    atividade = models.ForeignKey(
        "pedagogico.Atividade",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="relatorios",
        verbose_name="atividade",
    )
    tipo = models.CharField(
        max_length=10,
        choices=TIPOS_RELATORIO,
        default="geral",
    )
    disclaimer = models.TextField("disclaimer", blank=True, default="")

    class Meta(BaseModel.Meta):
        verbose_name = "relatório"
        verbose_name_plural = "relatórios"

    def __str__(self):
        return f"Relatório #{self.pk} (Aluno {self.aluno_id})"
