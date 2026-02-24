# Generated manually: backfill sku_canonico from sku

import re
from django.db import migrations


def normalize_sku_canonical(raw):
    if not raw or not isinstance(raw, str):
        return None
    s = str(raw).strip().upper().replace(" ", "").replace("_", "-")
    s = re.sub(r"-+", "-", s).strip("-").replace(",", ".")
    m = re.match(r"^(TWCAT)0+([0-9]+)(.*)$", s)
    if m:
        s = f"{m.group(1)}{int(m.group(2))}{m.group(3)}"
    m = re.match(r"^(CLF)([O0]+)(\d*)(.*)$", s)
    if m:
        s = f"{m.group(1)}{m.group(2).replace('O', '0')}{m.group(3)}{m.group(4)}"
    return s or None


def backfill_sku_canonico(apps, schema_editor):
    Product = apps.get_model("catalog", "Product")
    for p in Product.objects.only("id", "sku", "sku_canonico"):
        if p.sku and not p.sku_canonico:
            p.sku_canonico = normalize_sku_canonical(p.sku) or None
            p.save(update_fields=["sku_canonico"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("catalog", "0009_add_sku_canonico"),
    ]

    operations = [
        migrations.RunPython(backfill_sku_canonico, noop),
    ]
