from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Responsavel


@admin.register(Responsavel)
class ResponsavelAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ["id", "nome", "email", "cpf", "created_at", "deleted"]
    search_fields = ["nome", "email"]
