from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Turma


class ExcluidosFilter(admin.SimpleListFilter):
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


@admin.register(Turma)
class TurmaAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ("nome", "ano_letivo", "escola", "created_at", "deleted")
    list_filter = ("escola", "ano_letivo", ExcluidosFilter)
    search_fields = ("nome",)
    filter_horizontal = ("professores",)
