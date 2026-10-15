from django.conf import settings
from django.db import models

from core.models import BaseModel


class Item(BaseModel):
    title = models.CharField("título", max_length=200)
    description = models.TextField("descrição", blank=True)
    done = models.BooleanField("concluído", default=False)  # pyright: ignore[reportArgumentType]
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="items"
    )

    class Meta(BaseModel.Meta):
        verbose_name = "item"
        verbose_name_plural = "itens"

    def __str__(self):
        return str(self.title)
