from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0011_tag_post_tags"),
    ]

    operations = [
        migrations.AlterField(
            model_name="tag",
            name="slug",
            field=models.SlugField(allow_unicode=True, max_length=60, unique=True),
        ),
        migrations.CreateModel(
            name="TagSlugHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("old_slug", models.CharField(db_index=True, max_length=60, unique=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("tag", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="slug_history", to="blog.tag")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
