from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Consentimento


@admin.register(Consentimento)
class ConsentimentoAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = [
        "id",
        "aluno",
        "responsavel",
        "finalidade",
        "aceito_em",
        "revogado_em",
        "deleted",
    ]
    search_fields = ["aluno__nome"]
