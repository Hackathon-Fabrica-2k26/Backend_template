import pytest
from cryptography.fernet import Fernet
from django.db import connection

from apps.escolas.models import Config
from apps.escolas.utils.crypto import (
    decrypt_value,
    encrypt_value,
    get_fernet_key,
    is_encrypted,
)

pytestmark = pytest.mark.django_db


def test_valor_no_banco_e_cifrado_e_leitura_devolve_original():
    chave_original = "AIzaSyD-chave-secreta-gemini-2026"
    config = Config.objects.create(
        modelo="gemini-3.8-flash",
        api_key=chave_original,
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT api_key FROM escolas_config WHERE id = %s", [config.id])
        (valor_bruto_banco,) = cursor.fetchone()

    assert valor_bruto_banco != chave_original
    assert valor_bruto_banco.startswith("gAAAAA")
    assert is_encrypted(valor_bruto_banco) is True

    instancia = Config.objects.get(pk=config.pk)
    assert instancia.api_key == chave_original


def test_historico_salva_chave_cifrada():
    chave_original = "chave-gemini-com-historico"
    config = Config.objects.create(
        modelo="gemini-3.8-flash",
        api_key=chave_original,
    )

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT api_key FROM escolas_historicalconfig WHERE id = %s ORDER BY history_date DESC",
            [config.id],
        )
        (valor_bruto_historico,) = cursor.fetchone()

    assert valor_bruto_historico != chave_original
    assert valor_bruto_historico.startswith("gAAAAA")
    assert is_encrypted(valor_bruto_historico) is True

    historico = config.history.first()
    assert historico is not None
    assert historico.api_key == chave_original


def test_chave_vazia_permanece_vazia():
    config = Config.objects.create(
        modelo="gemini-3.8-flash",
        api_key="",
    )

    with connection.cursor() as cursor:
        cursor.execute("SELECT api_key FROM escolas_config WHERE id = %s", [config.id])
        (valor_bruto,) = cursor.fetchone()

    assert valor_bruto == ""

    instancia = Config.objects.get(pk=config.pk)
    assert instancia.api_key == ""


def test_leitura_de_dado_legado_em_texto_puro_e_compativel():
    config = Config.objects.create(
        modelo="gemini-legado",
        api_key="",
    )
    chave_legada = "chave-legada-sem-cifragem"

    with connection.cursor() as cursor:
        cursor.execute(
            "UPDATE escolas_config SET api_key = %s WHERE id = %s",
            [chave_legada, config.id],
        )

    instancia = Config.objects.get(pk=config.pk)
    assert instancia.api_key == chave_legada

    instancia.save()

    with connection.cursor() as cursor:
        cursor.execute("SELECT api_key FROM escolas_config WHERE id = %s", [config.id])
        (novo_valor_banco,) = cursor.fetchone()

    assert novo_valor_banco != chave_legada
    assert novo_valor_banco.startswith("gAAAAA")
    assert is_encrypted(novo_valor_banco) is True


def test_chave_fernet_customizada(settings):
    chave_custom = Fernet.generate_key().decode()
    settings.CONFIG_FERNET_KEY = chave_custom

    assert get_fernet_key() == chave_custom.encode()

    texto = "minha-chave-com-fernet-custom"
    cifrado = encrypt_value(texto)
    assert cifrado.startswith("gAAAAA")
    assert decrypt_value(cifrado) == texto


def test_protecao_dupla_cifragem_e_validacoes():
    assert encrypt_value("") == ""
    assert decrypt_value("") == ""
    assert is_encrypted("") is False
    assert is_encrypted(None) is False
    assert is_encrypted("chave-em-texto-puro") is False

    texto = "chave-de-teste-idempotente"
    cifrado = encrypt_value(texto)
    cifrado_novamente = encrypt_value(cifrado)
    assert cifrado_novamente == cifrado
