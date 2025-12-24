from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0008_country_iso_a2_country_iso_a3_country_name_en_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="SeedMeta",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(default="prod_seed", max_length=50, unique=True)),
                ("fixture_path", models.CharField(blank=True, default="", max_length=300)),
                ("fixture_sha256", models.CharField(blank=True, default="", max_length=64)),
                ("applied_at", models.DateTimeField(blank=True, null=True)),
                ("notes", models.JSONField(blank=True, default=dict)),
            ],
            options={
                "verbose_name": "Seed Meta",
                "verbose_name_plural": "Seed Meta",
            },
        ),
    ]
