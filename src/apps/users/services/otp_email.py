"""E-mail do código de verificação (OTP), em HTML com a identidade do Marsupi e texto puro."""

from email.mime.image import MIMEImage
from pathlib import Path

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .otp import OTP_TTL

LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "logo-email.png"
LOGO_CID = "logo-marsupi"


def contexto_email_otp(user, code: str, *, reenvio: bool = False, logo_src: str | None = None):
    nome = (getattr(user, "name", "") or "").strip().split(" ", 1)[0]
    return {
        "titulo": "Seu novo código de acesso" if reenvio else "Seu código de acesso",
        "nome": nome,
        "codigo": code,
        "digitos": list(code),
        "minutos": OTP_TTL // 60,
        "logo_src": logo_src or f"cid:{LOGO_CID}",
    }


def enviar_email_otp(user, code: str, *, reenvio: bool = False) -> None:
    contexto = contexto_email_otp(user, code, reenvio=reenvio)
    assunto = f"{code} é o seu código do Marsupi"
    mensagem = EmailMultiAlternatives(
        subject=assunto,
        body=render_to_string("users/email/otp.txt", contexto),
        to=[user.email],
    )
    mensagem.attach_alternative(render_to_string("users/email/otp.html", contexto), "text/html")
    # Logo embutida (cid) para aparecer sem baixar imagem externa.
    mensagem.mixed_subtype = "related"
    logo = MIMEImage(LOGO_PATH.read_bytes(), _subtype="png")
    logo.add_header("Content-ID", f"<{LOGO_CID}>")
    logo.add_header("Content-Disposition", "inline", filename="marsupi.png")
    mensagem.attach(logo)
    mensagem.send(fail_silently=False)
