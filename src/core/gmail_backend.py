"""Custom Django EmailBackend que envia e-mails via Gmail API."""

import base64
import json
import logging
import subprocess
import urllib.request
from email.mime.text import MIMEText

from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

_CRED_PATH = (
    "/home/matheus/.npm/_npx/d6e8705027e519a1/node_modules/"
    "@aaronsb/google-workspace-mcp/build/accounts/credentials.js"
)
NODE_AUTH_SCRIPT = f"""
import {{ readCredential }} from '{_CRED_PATH}';
const c = await readCredential('matheus.vidal.zenere@gmail.com');
const res = await fetch('https://oauth2.googleapis.com/token', {{
  method: 'POST',
  headers: {{ 'Content-Type': 'application/x-www-form-urlencoded' }},
  body: new URLSearchParams({{
    client_id: c.client_id,
    client_secret: c.client_secret,
    refresh_token: c.refresh_token,
    grant_type: 'refresh_token'
  }})
}});
const data = await res.json();
process.stdout.write(data.access_token || '');
"""


def get_gmail_access_token():
    try:
        token = subprocess.check_output(
            ["node", "--input-type=module", "-e", NODE_AUTH_SCRIPT],
            timeout=5,
        ).decode("utf-8").strip()
        return token if token else None
    except Exception as e:
        logger.error(f"Erro ao obter access token do Gmail: {e}")
        return None


class GmailApiEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        token = get_gmail_access_token()
        sent_count = 0

        for message in email_messages:
            try:
                # Imprime no console também para debug fácil
                print("\n" + "=" * 50)
                print(f"[MARSUPI EMAIL] Para: {', '.join(message.to)}")
                print(f"[MARSUPI EMAIL] Assunto: {message.subject}")
                print(f"[MARSUPI EMAIL] Conteúdo: {message.body}")
                print("=" * 50 + "\n")

                if token:
                    for recipient in message.to:
                        mime_msg = MIMEText(message.body, "plain", "utf-8")
                        mime_msg["to"] = recipient
                        mime_msg["from"] = "matheus.vidal.zenere@gmail.com"
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
                        )
                        with urllib.request.urlopen(req, timeout=10) as resp:
                            res_json = json.loads(resp.read().decode("utf-8"))
                            msg_id = res_json.get("id")
                            logger.info(f"E-mail enviado com sucesso via Gmail API! ID: {msg_id}")
                    sent_count += 1
                else:
                    sent_count += 1
            except Exception as e:
                logger.error(f"Falha ao enviar e-mail via Gmail API: {e}")
                if not self.fail_silently:
                    raise

        return sent_count
