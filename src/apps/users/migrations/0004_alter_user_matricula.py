from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_user_matricula"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="matricula",
            field=models.CharField(max_length=100, unique=True),
        ),
    ]
