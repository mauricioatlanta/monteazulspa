"""
Reporta productos duplicados por norm_key(sku).
Ej: 2X6 y 2-X-6 son el mismo producto con distinto formato.
"""
import re
from collections import defaultdict

from django.core.management.base import BaseCommand

from apps.catalog.models import Product


def norm_key(s: str) -> str:
    if not s:
        return ""
    s = s.strip().upper().replace(",", ".")
    s = re.sub(r"(\d+)\.(\d{1,2})", r"\1\2", s)
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


class Command(BaseCommand):
    help = "Reporta SKUs duplicados según clave normalizada (ej. 2X6 y 2-X-6)."

    def add_arguments(self, parser):
        parser.add_argument("--field", default="sku")

    def handle(self, *args, **opts):
        field = opts["field"]
        groups = defaultdict(list)

        for p in Product.objects.all().only("id", field):
            raw = getattr(p, field, "") or ""
            k = norm_key(raw)
            if k:
                groups[k].append((p.id, raw))

        dups = {k: v for k, v in groups.items() if len(v) > 1}
        if not dups:
            self.stdout.write("No duplicates.")
            return

        for k, items in sorted(dups.items(), key=lambda x: (-len(x[1]), x[0])):
            self.stdout.write(f"\nKEY={k}  count={len(items)}")
            for pid, raw in items:
                self.stdout.write(f"  - {pid}: {raw}")
