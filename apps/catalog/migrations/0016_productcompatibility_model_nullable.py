# -*- coding: utf-8 -*-
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0015_searchlog"),
    ]

    operations = [
        migrations.AlterField(
            model_name="productcompatibility",
            name="model",
            field=models.ForeignKey(
                blank=True,
                help_text="Si es NULL, compatibilidad amplia por marca (todos los modelos).",
                null=True,
                on_delete=models.PROTECT,
                to="catalog.vehiclemodel",
            ),
        ),
    ]
