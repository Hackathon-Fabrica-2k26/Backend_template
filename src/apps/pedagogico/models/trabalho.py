from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import BaseModel


class EnvioTrabalhos(BaseModel):
    atividade = models.ForeignKey(
        "pedagogico.Atividade",
        on_delete=models.CASCADE,
        related_name="envios_trabalhos",
        verbose_name="atividade",
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="envios_trabalhos",
        verbose_name="enviado por",
    )
    total_arquivos = models.PositiveIntegerField("total de arquivos", default=0)

    class Meta(BaseModel.Meta):
        verbose_name = "envio de trabalhos"
        verbose_name_plural = "envios de trabalhos"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Envio #{self.pk} (Atividade #{self.atividade_id})"


class Trabalho(BaseModel):
    """Trabalho de aluno analisado via IA.
    LGPD: A foto original não é persistida (descarte imediato após análise).
    """

    class IdentificacaoChoices(models.TextChoices):
        PENDENTE = "pendente", "Pendente"
        AUTOMATICA = "automatica", "Automática"
        CONFIRMADA = "confirmada", "Confirmada"
        SEM_ALUNO = "sem_aluno", "Sem aluno"
        SEM_CONSENTIMENTO = "sem_consentimento", "Sem consentimento"

    class StatusChoices(models.TextChoices):
        RECEBIDO = "recebido", "Recebido"
        ANALISANDO = "analisando", "Analisando"
        ANALISADO = "analisado", "Analisado"
        ERRO = "erro", "Erro"

    envio = models.ForeignKey(
        "pedagogico.EnvioTrabalhos",
        on_delete=models.CASCADE,
        related_name="trabalhos",
        verbose_name="envio",
    )
    atividade = models.ForeignKey(
        "pedagogico.Atividade",
        on_delete=models.CASCADE,
        related_name="trabalhos",
        verbose_name="atividade",
    )
    aluno = models.ForeignKey(
        "alunos.Aluno",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trabalhos",
        verbose_name="aluno",
    )
    variacao = models.ForeignKey(
        "pedagogico.AtividadeVariacao",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trabalhos",
        verbose_name="variação",
    )
    nome_lido = models.CharField(
        "nome lido",
        max_length=120,
        blank=True,
        default="",
    )
    confianca_nome = models.FloatField(
        "confiança do nome",
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
    )
    identificacao = models.CharField(
        "identificação",
        max_length=20,
        choices=IdentificacaoChoices.choices,
        default=IdentificacaoChoices.PENDENTE,
    )
    confirmado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="trabalhos_confirmados",
        verbose_name="confirmado por",
    )
    descricao_ia = models.TextField("descrição da IA", blank=True, default="")
    dados_analise = models.JSONField("dados da análise", default=dict, blank=True)
    status = models.CharField(
        "status",
        max_length=15,
        choices=StatusChoices.choices,
        default=StatusChoices.RECEBIDO,
    )

    class Meta(BaseModel.Meta):
        verbose_name = "trabalho"
        verbose_name_plural = "trabalhos"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(identificacao__in=["automatica", "confirmada"])
                    | models.Q(aluno__isnull=False)
                ),
                name="ck_trabalho_identificacao_exige_aluno",
            )
        ]

    def __str__(self):
        return f"Trabalho #{self.pk} (Atividade #{self.atividade_id})"
