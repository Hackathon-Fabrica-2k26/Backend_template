from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import (
    Atividade,
    AtividadeVariacao,
    EnvioTrabalhos,
    PerfilApoio,
    Trabalho,
    VariacaoAluno,
)


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
    list_display = ("titulo", "turma", "origem", "status", "criada_por", "created_at", "deleted")
    list_filter = ("status", "origem", "turma", ExcluidosFilter)
    search_fields = ("titulo", "objetivo")


@admin.register(AtividadeVariacao)
class AtividadeVariacaoAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ("rotulo", "atividade", "numero", "eh_geral", "status", "created_at", "deleted")
    list_filter = ("status", "eh_geral", ExcluidosFilter)
    search_fields = ("rotulo",)


@admin.register(VariacaoAluno)
class VariacaoAlunoAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ("variacao", "aluno", "created_at", "deleted")
    list_filter = (ExcluidosFilter,)


@admin.register(PerfilApoio)
class PerfilApoioAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ("id", "aluno", "ativo", "created_at", "deleted")
    list_filter = ("ativo", ExcluidosFilter)
    search_fields = ("aluno__nome",)


@admin.register(EnvioTrabalhos)
class EnvioTrabalhosAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ("id", "atividade", "enviado_por", "total_arquivos", "created_at", "deleted")
    list_filter = (ExcluidosFilter,)


@admin.register(Trabalho)
class TrabalhoAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = (
        "id",
        "atividade",
        "aluno",
        "identificacao",
        "status",
        "created_at",
        "deleted",
    )
    list_filter = ("identificacao", "status", ExcluidosFilter)
    search_fields = ("nome_lido",)
