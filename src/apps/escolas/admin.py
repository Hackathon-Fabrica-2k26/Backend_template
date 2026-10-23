from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from .models import Config, Escola, Turma


@admin.register(Config)
class ConfigAdmin(SimpleHistoryAdmin):
    list_display = ("id", "modelo")
    exclude = ("api_key",)


@admin.register(Escola)
class EscolaAdmin(SimpleHistoryAdmin):
    list_display = ("id", "nome", "endereco", "config")


@admin.register(Turma)
class TurmaAdmin(SimpleHistoryAdmin):
    list_display = ("id", "nome", "escola")
    filter_horizontal = ("professores",)