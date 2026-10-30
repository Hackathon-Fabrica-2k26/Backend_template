from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.core.exceptions import ValidationError

from apps.users.services.otp import create_otp, verify_otp
from apps.users.services.otp_email import enviar_email_otp


class AdminOTPAuthenticationForm(AdminAuthenticationForm):
    """Formulário de login do admin que exige OTP obrigatório para contas staff/superuser."""

    otp_code = forms.CharField(
        label="Código de verificação (OTP)",
        required=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "one-time-code",
                "placeholder": "Código de 4 dígitos",
            }
        ),
        help_text="Enviado por e-mail após preencher matrícula e senha.",
    )

    def clean(self):
        super().clean()
        user = self.user_cache
        if not user or not (user.is_staff or user.is_superuser):
            return self.cleaned_data

        otp_code = (self.cleaned_data.get("otp_code") or "").strip()
        session = getattr(self.request, "session", None)

        if not otp_code:
            # Primeiro passo: credenciais válidas. Gera o OTP e envia por e-mail.
            otp_token, code = create_otp(user.pk)
            enviar_email_otp(user, code)
            if session is not None:
                session["admin_otp_token"] = otp_token
                session["admin_otp_user_id"] = user.pk
                session.modified = True
            raise ValidationError(
                "Código de verificação enviado para o seu e-mail. "
                "Digite o código de 4 dígitos para concluir o login.",
                code="otp_required",
            )

        # Segundo passo: valida o código OTP fornecido
        otp_token = session.get("admin_otp_token") if session else None
        if not otp_token or session.get("admin_otp_user_id") != user.pk:
            otp_token, code = create_otp(user.pk)
            enviar_email_otp(user, code)
            if session is not None:
                session["admin_otp_token"] = otp_token
                session["admin_otp_user_id"] = user.pk
                session.modified = True
            raise ValidationError(
                "Código de verificação expirado ou ausente. "
                "Enviamos um novo código para seu e-mail.",
                code="otp_expired",
            )

        valid, user_id, error = verify_otp(otp_token, otp_code)
        if not valid or user_id != user.pk:
            raise ValidationError(
                error or "Código de verificação incorreto.",
                code="otp_invalid",
            )

        # Sucesso: limpa a chave da sessão
        if session is not None:
            session.pop("admin_otp_token", None)
            session.pop("admin_otp_user_id", None)
            session.modified = True

        return self.cleaned_data
