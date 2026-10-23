from django.db import models

from core.models import BaseModel


class Aluno(BaseModel):
    """Aluno do sistema.
    LGPD: Dados de menores e CPF de responsável nunca vão para a LLM.
    """

    nome = models.CharField("nome", max_length=45)

    meta_dados = models.OneToOneField(
        "MetaDados",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="aluno",
        verbose_name="meta dados",
    )

    responsavel = models.ForeignKey(
        "Responsavel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alunos",
        verbose_name="responsável",
    )

    turma = models.ForeignKey(
        "escolas.Turma",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="alunos",
        verbose_name="turma",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "aluno"
        verbose_name_plural = "alunos"
        ordering = ["nome"]

    def __str__(self):
        return self.nome
