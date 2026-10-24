from django.db import models

from core.models import BaseModel


class Responsavel(BaseModel):
    nome = models.CharField("nome", max_length=100)
    email = models.EmailField("e-mail", max_length=255, unique=True)
    telefone = models.CharField("telefone", max_length=20, blank=True)
    cpf = models.CharField("CPF", max_length=11, blank=True, default="")
    endereco = models.CharField("endereço", max_length=255, blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "responsável"
        verbose_name_plural = "responsáveis"
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.email})"
