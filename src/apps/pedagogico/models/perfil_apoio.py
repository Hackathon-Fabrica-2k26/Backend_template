from django.db import models

from core.models import BaseModel


class PerfilApoio(BaseModel):
    """Perfil de apoio pedagógico do aluno.
    LGPD: Sem CID nem diagnóstico clínico — apenas necessidades e estratégias pedagógicas.
    """

    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="perfis_apoio",
        verbose_name="aluno",
    )
    necessidades = models.JSONField("necessidades", default=list, blank=True)
    estrategias = models.JSONField("estratégias", default=list, blank=True)
    observacoes = models.TextField("observações", blank=True, default="")
    ativo = models.BooleanField("ativo", default=True)

    class Meta(BaseModel.Meta):
        verbose_name = "perfil de apoio"
        verbose_name_plural = "perfis de apoio"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["aluno"],
                condition=models.Q(ativo=True, deleted__isnull=True),
                name="uq_perfil_apoio_ativo_por_aluno",
            )
        ]

    def __str__(self):
        return f"Perfil de apoio #{self.pk} (Aluno #{self.aluno_id})"
