from django.db import models

from core.models import BaseModel


class Trabalho(BaseModel):
    """Trabalho individual enviado e analisado via IA."""

    class IdentificacaoChoices(models.TextChoices):
        CONFIRMADA = "confirmada", "Confirmada"
        PENDENTE = "pendente", "Pendente"
        MANUAL = "manual", "Manual"

    envio = models.ForeignKey(
        "EnvioTrabalhos",
        on_delete=models.CASCADE,
        related_name="trabalhos",
        verbose_name="envio",
    )
    atividade = models.ForeignKey(
        "Atividade",
        on_delete=models.CASCADE,
        related_name="trabalhos",
        verbose_name="atividade",
    )
    aluno = models.ForeignKey(
        "alunos.Aluno",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trabalhos",
        verbose_name="aluno",
    )
    nome_lido = models.CharField("nome lido", max_length=255, blank=True, default="")
    confianca = models.FloatField("confiança", default=0.0)
    identificacao = models.CharField(
        "identificação",
        max_length=20,
        choices=IdentificacaoChoices.choices,
        default=IdentificacaoChoices.PENDENTE,
    )
    descricao_ia = models.TextField("descrição da IA", blank=True, default="")
    analise_pedagogica = models.JSONField("análise pedagógica", default=dict, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "trabalho"
        verbose_name_plural = "trabalhos"
        ordering = ["-created_at"]

    def __str__(self):
        aluno_nome = self.aluno.nome if self.aluno else (self.nome_lido or "Não identificado")
        return f"Trabalho #{self.pk} - {aluno_nome} ({self.identificacao})"
