import apps.escolas.fields
from django.db import migrations


def cifrar_chaves_existentes(apps, schema_editor):
    from apps.escolas.utils.crypto import encrypt_value, is_encrypted

    Config = apps.get_model("escolas", "Config")
    for obj in Config.objects.all():
        if obj.api_key and not is_encrypted(obj.api_key):
            obj.api_key = encrypt_value(obj.api_key)
            obj.save(update_fields=["api_key"])

    HistoricalConfig = apps.get_model("escolas", "HistoricalConfig")
    for obj in HistoricalConfig.objects.all():
        if obj.api_key and not is_encrypted(obj.api_key):
            obj.api_key = encrypt_value(obj.api_key)
            obj.save(update_fields=["api_key"])


def reverter_cifra_chaves(apps, schema_editor):
    from apps.escolas.utils.crypto import decrypt_value, is_encrypted

    Config = apps.get_model("escolas", "Config")
    for obj in Config.objects.all():
        if obj.api_key and is_encrypted(obj.api_key):
            obj.api_key = decrypt_value(obj.api_key)
            obj.save(update_fields=["api_key"])

    HistoricalConfig = apps.get_model("escolas", "HistoricalConfig")
    for obj in HistoricalConfig.objects.all():
        if obj.api_key and is_encrypted(obj.api_key):
            obj.api_key = decrypt_value(obj.api_key)
            obj.save(update_fields=["api_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("escolas", "0003_historicalturma_ano_letivo_turma_ano_letivo"),
    ]

    operations = [
        migrations.AlterField(
            model_name="config",
            name="api_key",
            field=apps.escolas.fields.EncryptedCharField(max_length=512),
        ),
        migrations.AlterField(
            model_name="historicalconfig",
            name="api_key",
            field=apps.escolas.fields.EncryptedCharField(max_length=512),
        ),
        migrations.RunPython(cifrar_chaves_existentes, reverter_cifra_chaves),
    ]
