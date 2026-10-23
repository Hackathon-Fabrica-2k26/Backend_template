from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import MetaDados


@admin.register(MetaDados)
class MetaDadosAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    list_display = ["id", "perfil_disc", "created_at", "deleted"]
    search_fields = ["perfil_disc"]
