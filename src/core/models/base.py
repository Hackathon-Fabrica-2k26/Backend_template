from django.db import models
from safedelete.models import SOFT_DELETE_CASCADE, SafeDeleteModel
from simple_history.models import HistoricalRecords


class BaseModel(SafeDeleteModel):
    """Base dos modelos: timestamps, histórico de alterações e exclusão lógica."""

    _safedelete_policy = SOFT_DELETE_CASCADE

    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)
    history = HistoricalRecords(inherit=True)

    class Meta(SafeDeleteModel.Meta):
        abstract = True
        ordering = ["-created_at"]

    def delete(self, force_policy=None, **kwargs):
        self._change_reason = "Exclusão lógica"
        return super().delete(force_policy=force_policy, **kwargs)

    def undelete(self, force_policy=None, **kwargs):
        self._change_reason = "Restauração"
        return super().undelete(force_policy=force_policy, **kwargs)
