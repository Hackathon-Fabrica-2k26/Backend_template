from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from unfold.admin import ModelAdmin
from unfold.forms import AdminPasswordChangeForm
from unfold.forms import UserChangeForm as UnfoldUserChangeForm
from unfold.forms import UserCreationForm as UnfoldUserCreationForm

from ..models import User
from .forms import AdminOTPAuthenticationForm

admin.site.login_form = AdminOTPAuthenticationForm


class UserCreationForm(UnfoldUserCreationForm):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = User
        fields = ("email", "name", "matricula")


class UserChangeForm(UnfoldUserChangeForm):
    class Meta:  # pyright: ignore[reportIncompatibleVariableOverride]
        model = User
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "otp_ativo" in self.fields:
            self.fields["otp_ativo"].help_text = (
                "Para contas comuns (professores), ativa o envio de código por e-mail no login. "
                "Para equipe (is_staff e superusuários), o 2FA é obrigatório por padrão."
            )


@admin.register(User)
class UserAdmin(BaseUserAdmin, ModelAdmin):  # pyright: ignore[reportIncompatibleMethodOverride, reportGeneralTypeIssues]
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm

    list_display = ("email", "name", "matricula", "is_staff", "is_active", "date_joined")
    list_filter = ("is_staff", "is_superuser", "is_active")
    search_fields = ("email", "name")
    ordering = ("-date_joined",)

    fieldsets = (
        (None, {"fields": ("email", "password", "matricula")}),
        ("Dados pessoais", {"fields": ("name",)}),
        ("Escola", {"fields": ("escola", "ano")}),
        ("Segurança", {"fields": ("otp_ativo",)}),
        (
            "Permissões",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("matricula", "email", "name", "password1", "password2"),
            },
        ),
    )
