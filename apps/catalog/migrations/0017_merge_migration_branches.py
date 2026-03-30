# -*- coding: utf-8 -*-
"""
Migración de merge para resolver conflicto entre ramas de desarrollo.
Esta migración permite que el servidor sincronice correctamente.
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0016_productcompatibility_model_nullable"),
        # Si el servidor tiene 0016_add_recommended_displacement_to_product, 
        # esta migración la reemplaza sin conflicto
    ]

    operations = [
        # No hace cambios en la BD, solo resuelve el árbol de dependencias
    ]
