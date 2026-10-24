from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Trabalho
from .atividade import ExcluidosFilter


@admin.register(Trabalho)
class TrabalhoAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = (
        "id",
        "atividade",
        "aluno",
        "nome_lido",
        "confianca",
        "identificacao",
        "created_at",
        "deleted",
    )
    list_filter = ("identificacao", ExcluidosFilter)
    search_fields = ("nome_lido", "aluno__nome", "atividade__nome")
