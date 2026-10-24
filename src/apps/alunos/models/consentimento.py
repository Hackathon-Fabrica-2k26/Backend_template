from django.db import models

from core.models import BaseModel

FINALIDADE_PADRAO = "analise_pedagogica_ia"
VERSAO_TEXTO_PADRAO = "v1"


class Consentimento(BaseModel):
    """Consentimento do responsável para tratamento do aluno por IA (LGPD, Art. 14).
    Sem consentimento ativo (não revogado), o aluno não passa pela IA.
    """

    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="consentimentos",
        verbose_name="aluno",
    )
    responsavel = models.ForeignKey(
        "alunos.Responsavel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="consentimentos",
        verbose_name="responsável",
    )
    finalidade = models.CharField("finalidade", max_length=100, default=FINALIDADE_PADRAO)
    versao_texto = models.CharField("versão do texto", max_length=20, default=VERSAO_TEXTO_PADRAO)
    aceito_em = models.DateTimeField("aceito em")
    revogado_em = models.DateTimeField("revogado em", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "consentimento"
        verbose_name_plural = "consentimentos"
        ordering = ["-aceito_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno", "finalidade"],
                condition=models.Q(revogado_em__isnull=True, deleted__isnull=True),
                name="uq_consentimento_ativo_por_aluno_finalidade",
            )
        ]

    @property
    def ativo(self) -> bool:
        return self.revogado_em is None

    def __str__(self):
        return f"Consentimento #{self.pk} (Aluno #{self.aluno_id})"
