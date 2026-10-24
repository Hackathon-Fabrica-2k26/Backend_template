from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import EnvioTrabalhos
from .atividade import ExcluidosFilter


@admin.register(EnvioTrabalhos)
class EnvioTrabalhosAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = (
        "id",
        "atividade",
        "enviado_por",
        "total_arquivos",
        "status",
        "created_at",
        "deleted",
    )
    list_filter = ("status", ExcluidosFilter)
    search_fields = ("atividade__nome", "enviado_por__name", "enviado_por__email")
