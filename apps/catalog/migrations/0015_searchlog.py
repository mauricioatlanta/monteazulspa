from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0014_add_recommended_cc_range"),
    ]

    operations = [
        migrations.CreateModel(
            name="SearchLog",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("query", models.CharField(max_length=255)),
                ("cc", models.IntegerField(blank=True, null=True, db_index=True)),
                ("fuel", models.CharField(max_length=20, blank=True, null=True, db_index=True)),
                ("year", models.IntegerField(blank=True, null=True, db_index=True)),
                ("results_count", models.IntegerField()),
                ("is_relaxed", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]

