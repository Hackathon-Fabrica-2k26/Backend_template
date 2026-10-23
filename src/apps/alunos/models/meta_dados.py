from django.db import models

from core.models import BaseModel


class MetaDados(BaseModel):
    PERFIL_DISC_CHOICES = [
        ("D", "Dominância"),
        ("I", "Influência"),
        ("S", "Estabilidade"),
        ("C", "Conformidade"),
    ]

    perfil_disc = models.CharField(
        "perfil DISC",
        max_length=1,
        choices=PERFIL_DISC_CHOICES,
        blank=True,
    )
    caracteristicas = models.JSONField("características", default=dict)

    class Meta(BaseModel.Meta):
        verbose_name = "meta dado"
        verbose_name_plural = "meta dados"
        ordering = ["perfil_disc"]

    def __str__(self):
        return f"Perfil {self.perfil_disc}"
