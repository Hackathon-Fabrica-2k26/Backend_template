"""Backend de e-mail customizado para envio via Gmail API (OAuth 2.0)."""

import base64
import json
import logging
import os
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


def _load_credentials():
    """Localiza e carrega credenciais OAuth 2.0 para acesso à API do Gmail.

    Ordem de busca:
    1. Variável de ambiente GMAIL_CREDENTIALS_FILE.
    2. Variável de ambiente GOOGLE_APPLICATION_CREDENTIALS.
    3. Variáveis diretas GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN.
    4. Diretório local do Google Workspace MCP em ~/.local/share/google-workspace-mcp/credentials/.
    """
    custom_path = os.getenv("GMAIL_CREDENTIALS_FILE") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if custom_path and Path(custom_path).is_file():
        try:
            with open(custom_path, encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("Falha ao carregar credenciais de %s: %s", custom_path, e)

    client_id = os.getenv("GMAIL_CLIENT_ID")
    client_secret = os.getenv("GMAIL_CLIENT_SECRET")
    refresh_token = os.getenv("GMAIL_REFRESH_TOKEN")
    if client_id and client_secret and refresh_token:
        return {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        }

    mcp_dir = Path.home() / ".local" / "share" / "google-workspace-mcp" / "credentials"
    if mcp_dir.is_dir():
        for file in mcp_dir.glob("*.json"):
            try:
                with open(file, encoding="utf-8") as f:
                    data = json.load(f)
                    if "refresh_token" in data and "client_id" in data:
                        return data
            except Exception as e:
                logger.warning("Falha ao ler arquivo de credencial %s: %s", file, e)

    return None


def get_gmail_access_token():
    """Obtém um access token atualizado via endpoint OAuth2 do Google."""
    creds = _load_credentials()
    if not creds:
        return None

    try:
        data = urllib.parse.urlencode(
            {
                "client_id": creds.get("client_id", ""),
                "client_secret": creds.get("client_secret", ""),
                "refresh_token": creds.get("refresh_token", ""),
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")

        req = urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=data,
            method="POST",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return payload.get("access_token")
    except Exception as e:
        logger.error("Erro ao obter access token do Gmail: %s", e)
        return None


class GmailApiEmailBackend(BaseEmailBackend):
    """EmailBackend que envia mensagens via Gmail REST API e imprime no terminal."""

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.sender = (
            os.getenv("GMAIL_SENDER")
            or os.getenv("DEFAULT_FROM_EMAIL")
            or "matheus.vidal.zenere@gmail.com"
        )
        self.dev_override = os.getenv("DEV_EMAIL_OVERRIDE", "")

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        token = get_gmail_access_token()
        sent_count = 0

        for message in email_messages:
            recipients = list(message.to)
            # Imprime no terminal para desenvolvimento e depuração local
            print("\n" + "=" * 50)
            print(f"[MARSUPI EMAIL] Para: {', '.join(recipients)}")
            print(f"[MARSUPI EMAIL] Assunto: {message.subject}")
            print(f"[MARSUPI EMAIL] Conteúdo: {message.body}")
            print("=" * 50 + "\n")

            if not token:
                sent_count += 1
                continue

            try:
                # Se houver DEV_EMAIL_OVERRIDE, redireciona o envio real
                destinations = [self.dev_override] if self.dev_override else recipients

                for dest in destinations:
                    mime_msg = MIMEText(message.body, "plain", "utf-8")
                    mime_msg["to"] = dest
                    mime_msg["from"] = self.sender
                    mime_msg["subject"] = message.subject

                    raw = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("utf-8")
                    payload = json.dumps({"raw": raw}).encode("utf-8")

                    req = urllib.request.Request(
                        "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                        data=payload,
                        headers={
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json",
                        },
                        method="POST",
                    )
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        res = json.loads(resp.read().decode("utf-8"))
                        logger.info(
                            "E-mail enviado via Gmail API para %s! ID: %s",
                            dest,
                            res.get("id"),
                        )
                sent_count += 1
            except Exception as e:
                logger.error("Falha ao enviar e-mail via Gmail API: %s", e)
                if not self.fail_silently:
                    raise

        return sent_count
