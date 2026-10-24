from django import forms
from django.contrib import admin
from safedelete.admin import SafeDeleteAdmin
from simple_history.admin import SimpleHistoryAdmin
from unfold.admin import ModelAdmin

from ..models import Config


class ExcluidosFilter(admin.SimpleListFilter):
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


class ConfigAdminForm(forms.ModelForm):
    """A chave nunca é exibida: o campo vem vazio e só grava quando preenchido."""

    api_key = forms.CharField(
        label="Chave da API (Gemini)",
        required=False,
        widget=forms.PasswordInput(render_value=False),
        help_text="Deixe em branco para manter a chave atual.",
    )

    class Meta:
        model = Config
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # {} é válido (sem campos extras); sem isso o admin recusa salvar.
        self.fields["campos_form"].required = False

    def clean_campos_form(self):
        return self.cleaned_data.get("campos_form") or {}


@admin.register(Config)
class ConfigAdmin(SafeDeleteAdmin, SimpleHistoryAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride]
    form = ConfigAdminForm
    list_display = ("modelo", "chave_configurada", "created_at", "deleted")
    list_filter = (ExcluidosFilter,)
    search_fields = ("modelo",)

    @admin.display(description="chave configurada", boolean=True)
    def chave_configurada(self, obj):
        return bool(obj.api_key)

    def save_model(self, request, obj, form, change):
        nova_chave = form.cleaned_data.get("api_key")
        if nova_chave:
            obj.api_key = nova_chave.strip()
        elif change:
            obj.api_key = Config.all_objects.get(pk=obj.pk).api_key
        super().save_model(request, obj, form, change)
