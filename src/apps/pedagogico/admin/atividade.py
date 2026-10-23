from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Atividade


class ExcluidosFilter(admin.SimpleListFilter):
    """Mostra ativos e excluídos por padrão; permite isolar um dos dois."""

    title = "exclusão"
    parameter_name = "excluidos"

    def lookups(self, request, model_admin):
        return (("nao", "Somente ativos"), ("sim", "Somente excluídos"))

    def queryset(self, request, queryset):
        if self.value() == "sim":
            return queryset.filter(deleted__isnull=False)
        if self.value() == "nao":
            return queryset.filter(deleted__isnull=True)
        return queryset


@admin.register(Atividade)
class AtividadeAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ("nome", "tipo", "aluno", "created_at", "deleted")
    list_filter = ("tipo", ExcluidosFilter)
    search_fields = ("nome", "tipo")
