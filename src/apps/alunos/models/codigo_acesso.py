from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import BaseModel


class CodigoAcessoAluno(BaseModel):
    """Código de acesso único gerado pela professora para vincular o responsável ao aluno.

    LGPD / Segurança: o código em claro só é exibido uma vez no momento da geração;
    no banco armazena-se exclusivamente `codigo_hash`.
    """

    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.CASCADE,
        related_name="codigos_acesso",
        verbose_name="aluno",
    )
    codigo_hash = models.CharField("hash do código", max_length=128, unique=True)
    gerado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="codigos_acesso_gerados",
        verbose_name="gerado por",
    )
    gerado_em = models.DateTimeField("gerado em", default=timezone.now)
    expira_em = models.DateTimeField("expira em")
    usado_em = models.DateTimeField("usado em", null=True, blank=True)
    revogado_em = models.DateTimeField("revogado em", null=True, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "código de acesso do aluno"
        verbose_name_plural = "códigos de acesso dos alunos"
        ordering = ["-gerado_em"]

    @property
    def esta_expirado(self) -> bool:
        return self.expira_em <= timezone.now()

    @property
    def esta_usado(self) -> bool:
        return self.usado_em is not None

    @property
    def esta_revogado(self) -> bool:
        return self.revogado_em is not None

    @property
    def esta_valido(self) -> bool:
        return not (self.esta_expirado or self.esta_usado or self.esta_revogado)

    def __str__(self):
        return f"Código #{self.pk} (Aluno #{self.aluno_id})"
