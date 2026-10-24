from django.db import models
from django.utils import timezone

from core.models import BaseModel


class Responsavel(BaseModel):
    nome = models.CharField("nome", max_length=100)
    email = models.EmailField("e-mail", max_length=255, blank=True, default="")
    telefone = models.CharField("telefone", max_length=20, blank=True, default="")
    cpf = models.CharField("CPF", max_length=11, blank=True, default="")

    class Meta(BaseModel.Meta):
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.email})" if self.email else self.nome


class AlunoResponsavel(BaseModel):
    """Vínculo N:N entre Aluno e Responsavel com parentesco."""

    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="vinculos_responsaveis",
        verbose_name="aluno",
    )
    responsavel = models.ForeignKey(
        "alunos.Responsavel",
        on_delete=models.CASCADE,
        related_name="vinculos_alunos",
        verbose_name="responsável",
    )
    parentesco = models.CharField("parentesco", max_length=30, blank=True, default="")
    vinculado_em = models.DateTimeField("vinculado em", default=timezone.now)

    class Meta(BaseModel.Meta):
        verbose_name = "vínculo aluno-responsável"
        verbose_name_plural = "vínculos aluno-responsável"
        ordering = ["-vinculado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "responsavel"],
                condition=models.Q(deleted__isnull=True),
                name="uq_aluno_responsavel_ativo",
            )
        ]

    def __str__(self):
        return f"Aluno #{self.aluno_id} <-> Responsável #{self.responsavel_id}"
