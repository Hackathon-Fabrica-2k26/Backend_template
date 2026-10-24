from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import AlunoResponsavel, CodigoAcessoAluno


@admin.register(CodigoAcessoAluno)
class CodigoAcessoAlunoAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = [
        "id",
        "aluno",
        "gerado_por",
        "gerado_em",
        "expira_em",
        "usado_em",
        "revogado_em",
    ]
    search_fields = ["aluno__nome"]
    exclude = ["codigo_hash"]


@admin.register(AlunoResponsavel)
class AlunoResponsavelAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ["id", "aluno", "responsavel", "parentesco", "vinculado_em", "deleted"]
    search_fields = ["aluno__nome", "responsavel__nome"]
