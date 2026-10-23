from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin as UnfoldModelAdmin

from ..models import Aluno


@admin.register(Aluno)
class AlunoAdmin(UnfoldModelAdmin, SimpleHistoryAdmin):
    list_display = ["id", "nome", "meta_dados", "responsavel"]
    search_fields = ["nome"]
