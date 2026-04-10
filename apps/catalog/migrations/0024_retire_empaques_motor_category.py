# -*- coding: utf-8 -*-
from django.db import migrations
from django.db.models import Q


REMOVED_TEXT_TERMS = (
    "empaque",
    "empaques",
    "empaquetadura",
    "empaquetaduras",
)

REMOVED_CATEGORY_SLUGS = (
    "empaquetaduras-de-motor",
    "empaques-de-motor",
    "empaque-de-motor",
    "empaquetadura-de-motor",
    "empaquetaduras-motor",
    "juntas-de-motor",
    "juntas-motor",
)


def retire_empaques_motor(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")
    Product = apps.get_model("catalog", "Product")

    category_q = Q(slug__in=REMOVED_CATEGORY_SLUGS)
    for term in REMOVED_TEXT_TERMS:
        category_q |= Q(name__icontains=term)

    Category.objects.filter(category_q).update(is_active=False)

    product_q = Q(category__slug__in=REMOVED_CATEGORY_SLUGS)
    for term in REMOVED_TEXT_TERMS:
        product_q |= Q(category__name__icontains=term)
        product_q |= Q(name__icontains=term)
        product_q |= Q(slug__icontains=term)

    Product.objects.filter(product_q).update(is_active=False, is_publishable=False)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0023_alter_searchlog_id"),
    ]

    operations = [
        migrations.RunPython(retire_empaques_motor, migrations.RunPython.noop),
    ]
