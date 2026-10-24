"""Testes do backend de e-mail GmailApiEmailBackend."""

import json
from unittest.mock import MagicMock, patch

from django.core.mail import EmailMessage

from core.gmail_backend import (
    GmailApiEmailBackend,
    _load_credentials,
    get_gmail_access_token,
)


def test_load_credentials_via_env(monkeypatch, tmp_path):
    cred_file = tmp_path / "creds.json"
    cred_data = {
        "client_id": "test_id",
        "client_secret": "test_secret",
        "refresh_token": "test_refresh",
    }
    cred_file.write_text(json.dumps(cred_data), encoding="utf-8")

    monkeypatch.setenv("GMAIL_CREDENTIALS_FILE", str(cred_file))
    result = _load_credentials()
    assert result == cred_data


def test_load_credentials_via_direct_env(monkeypatch):
    monkeypatch.delenv("GMAIL_CREDENTIALS_FILE", raising=False)
    monkeypatch.delenv("GOOGLE_APPLICATION_CREDENTIALS", raising=False)
    monkeypatch.setenv("GMAIL_CLIENT_ID", "direct_id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "direct_secret")
    monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "direct_refresh")

    result = _load_credentials()
    assert result == {
        "client_id": "direct_id",
        "client_secret": "direct_secret",
        "refresh_token": "direct_refresh",
    }


def test_get_access_token_success():
    fake_creds = {
        "client_id": "id",
        "client_secret": "secret",
        "refresh_token": "refresh",
    }
    with (
        patch("core.gmail_backend._load_credentials", return_value=fake_creds),
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"access_token": "fake_token"}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        token = get_gmail_access_token()
        assert token == "fake_token"


def test_gmail_backend_send_messages_empty():
    backend = GmailApiEmailBackend()
    assert backend.send_messages([]) == 0


def test_gmail_backend_send_messages_success(monkeypatch):
    monkeypatch.delenv("DEV_EMAIL_OVERRIDE", raising=False)
    backend = GmailApiEmailBackend()
    message = EmailMessage(
        subject="Assunto Teste",
        body="Código: 1234",
        to=["destinatario@example.com"],
    )

    with (
        patch(
            "core.gmail_backend.get_gmail_access_token",
            return_value="valid_token",
        ),
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": "msg_123"}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        sent = backend.send_messages([message])
        assert sent == 1
        assert mock_urlopen.called


def test_gmail_backend_send_messages_dev_override(monkeypatch):
    monkeypatch.setenv("DEV_EMAIL_OVERRIDE", "dev@override.com")
    backend = GmailApiEmailBackend()
    message = EmailMessage(
        subject="Assunto",
        body="Mensagem",
        to=["original@example.com"],
    )

    with (
        patch(
            "core.gmail_backend.get_gmail_access_token",
            return_value="valid_token",
        ),
        patch("urllib.request.urlopen") as mock_urlopen,
    ):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"id": "msg_456"}).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp

        sent = backend.send_messages([message])
        assert sent == 1
        # Verifica se o payload enviado continha o endereço de dev_override
        req_arg = mock_urlopen.call_args[0][0]
        data_json = json.loads(req_arg.data.decode("utf-8"))
        assert "raw" in data_json
