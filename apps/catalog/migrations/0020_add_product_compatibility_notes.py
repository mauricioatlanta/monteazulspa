# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0019_merge_0016_0018"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="compatibility_notes",
            field=models.TextField(
                blank=True,
                default="",
                help_text="Texto opcional que se muestra en la sección Compatibilidad vehicular: años, generación del modelo, otros vehículos que usan el mismo convertidor, etc.",
                verbose_name="Notas de compatibilidad (años, generaciones, otros modelos)",
            ),
        ),
    ]
