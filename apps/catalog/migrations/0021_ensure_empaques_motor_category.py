# -*- coding: utf-8 -*-
from django.db import migrations


def ensure_empaques_motor_category(apps, schema_editor):
    Category = apps.get_model("catalog", "Category")

    canonical_slug = "empaquetaduras-de-motor"
    canonical_name = "Empaques de Motor"

    slug_candidates = [
        canonical_slug,
        "empaques-de-motor",
        "empaque-de-motor",
        "empaquetadura-de-motor",
        "juntas-de-motor",
        "juntas-motor",
    ]
    name_candidates = [
        canonical_name,
        "Empaquetaduras de Motor",
        "Juntas de Motor",
        "Juntas Motor",
    ]

    cat = None
    for s in slug_candidates:
        cat = Category.objects.filter(slug=s).first()
        if cat:
            break

    if not cat:
        for n in name_candidates:
            cat = Category.objects.filter(name=n).first()
            if cat:
                break

    if cat:
        if cat.is_active is False:
            cat.is_active = True
        if cat.name != canonical_name:
            existing_by_name = Category.objects.filter(name=canonical_name).exclude(pk=cat.pk).first()
            if existing_by_name:
                if existing_by_name.is_active is False:
                    existing_by_name.is_active = True
                existing_by_name.save(update_fields=["is_active"])
            else:
                cat.name = canonical_name
        if cat.slug != canonical_slug:
            existing_by_slug = Category.objects.filter(slug=canonical_slug).exclude(pk=cat.pk).first()
            if not existing_by_slug:
                cat.slug = canonical_slug
        cat.save()
        return

    existing_by_name = Category.objects.filter(name=canonical_name).first()
    if existing_by_name:
        if existing_by_name.slug != canonical_slug and not Category.objects.filter(slug=canonical_slug).exclude(pk=existing_by_name.pk).exists():
            existing_by_name.slug = canonical_slug
        if existing_by_name.is_active is False:
            existing_by_name.is_active = True
        existing_by_name.save()
        return

    Category.objects.create(name=canonical_name, slug=canonical_slug, is_active=True)


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0020_add_product_compatibility_notes"),
    ]

    operations = [
        migrations.RunPython(ensure_empaques_motor_category, migrations.RunPython.noop),
    ]

