from django.conf import settings
from django.db import models

from core.models import BaseModel


class AtividadeVariacao(BaseModel):
    class StatusChoices(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        APROVADA = "aprovada", "Aprovada"
        DESCARTADA = "descartada", "Descartada"

    atividade = models.ForeignKey(
        "pedagogico.Atividade",
        on_delete=models.CASCADE,
        related_name="variacoes",
        verbose_name="atividade",
    )
    numero = models.PositiveIntegerField("número")
    rotulo = models.CharField("rótulo", max_length=40)
    eh_geral = models.BooleanField("é versão geral", default=False)
    conteudo = models.TextField("conteúdo")
    status = models.CharField(
        "status",
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.RASCUNHO,
    )
    editada_manual = models.BooleanField("editada manualmente", default=False)
    adaptacoes_feitas = models.JSONField("adaptações feitas", default=list, blank=True)
    aprovada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="variacoes_aprovadas",
        verbose_name="aprovada por",
    )
    aprovada_em = models.DateTimeField("aprovada em", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "variação de atividade"
        verbose_name_plural = "variações de atividade"
        ordering = ["atividade", "numero"]
        constraints = [
            models.UniqueConstraint(
                fields=["atividade", "numero"],
                name="uq_variacao_atividade_numero",
            )
        ]

    def __str__(self):
        return f"{self.rotulo} (Atividade #{self.atividade_id})"

    @property
    def alunos(self):
        from apps.alunos.models import Aluno

        return Aluno.objects.filter(
            variacoes_atribuidas__variacao=self,
            variacoes_atribuidas__deleted__isnull=True,
        )


class VariacaoAluno(BaseModel):
    variacao = models.ForeignKey(
        "pedagogico.AtividadeVariacao",
        on_delete=models.CASCADE,
        related_name="atribuicoes",
        verbose_name="variação",
    )
    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="variacoes_atribuidas",
        verbose_name="aluno",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "atribuição de variação"
        verbose_name_plural = "atribuições de variação"
        constraints = [
            models.UniqueConstraint(
                fields=["variacao", "aluno"],
                name="uq_variacao_aluno",
            )
        ]

    def __str__(self):
        return f"Variação #{self.variacao_id} -> Aluno #{self.aluno_id}"
