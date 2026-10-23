from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import MetaDados


@admin.register(MetaDados)
class MetaDadosAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ["id", "perfil_disc"]
    search_fields = ["perfil_disc"]
