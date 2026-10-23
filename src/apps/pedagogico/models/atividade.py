from django.db import models

from core.models import BaseModel


class Atividade(BaseModel):
    nome = models.CharField("nome", max_length=45)
    tipo = models.CharField("tipo", max_length=45)
    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="atividades",
        verbose_name="aluno",
    )
    relatorios = models.ManyToManyField(
        "Relatorio",
        related_name="atividades",
        blank=True,
        verbose_name="relatórios",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "atividade"
        verbose_name_plural = "atividades"

    def __str__(self):
        return str(self.nome)
