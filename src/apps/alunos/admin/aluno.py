from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Aluno


@admin.register(Aluno)
class AlunoAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = [
        "id",
        "nome",
        "matricula",
        "nascimento",
        "ativo",
        "turma",
        "meta_dados",
        "responsavel",
        "created_at",
        "deleted",
    ]
    search_fields = ["nome", "matricula"]
