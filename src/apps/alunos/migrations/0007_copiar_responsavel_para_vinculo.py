from django.db import migrations


def copiar_fk_para_vinculo(apps, schema_editor):
    """Copia Aluno.responsavel (FK legada) para o vínculo N:N AlunoResponsavel."""
    Aluno = apps.get_model("alunos", "Aluno")
    AlunoResponsavel = apps.get_model("alunos", "AlunoResponsavel")
    existentes = set(AlunoResponsavel.objects.values_list("aluno_id", "responsavel_id"))
    novos = []
    for aluno in Aluno.objects.filter(responsavel__isnull=False).iterator():
        if (aluno.pk, aluno.responsavel_id) in existentes:
            continue
        novos.append(
            AlunoResponsavel(
                aluno_id=aluno.pk,
                responsavel_id=aluno.responsavel_id,
                deleted=aluno.deleted,
            )
        )
    AlunoResponsavel.objects.bulk_create(novos, batch_size=500)


class Migration(migrations.Migration):
    dependencies = [
        ("alunos", "0006_codigo_acesso_vinculo_responsavel"),
    ]

    operations = [
        # Reversão: a FK Aluno.responsavel continua existindo, então não há o que desfazer.
        migrations.RunPython(copiar_fk_para_vinculo, migrations.RunPython.noop),
    ]