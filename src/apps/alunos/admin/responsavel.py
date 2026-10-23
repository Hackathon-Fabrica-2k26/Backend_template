from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Responsavel


@admin.register(Responsavel)
class ResponsavelAdmin(ModelAdmin, SimpleHistoryAdmin):
    list_display = ["id", "nome", "email", "cpf"]
    search_fields = ["nome", "email"]
    list_filter = ["nome"]
