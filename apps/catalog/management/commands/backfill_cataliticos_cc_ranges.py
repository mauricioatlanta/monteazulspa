# -*- coding: utf-8 -*-
"""
Backfill de recommended_cc_min, recommended_cc_max y combustible en productos
catalíticos según reglas por SKU/nombre.

Las reglas más específicas deben ir antes que las genéricas (p. ej. diesel
ovalado TWCAT002 antes que CAT002 bencina).
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Product


def _norm(s):
    """Texto normalizado para matching: mayúsculas, sin espacios ni guiones."""
    if s is None:
        return ""
    return str(s).upper().replace(" ", "").replace("-", "")


# Orden: primero reglas diesel específicas, luego CAT002 bencina y resto.
RULES = [
    # DIESEL / PETROLEROS - primero las específicas
    {"match": ["3222D"], "cc_min": 1800, "cc_max": 2200, "fuel": "DIESEL"},
    {
        "match": [
            "DIESEL TWCAT052 REDONDO 16 CMS 2 PULGADAS",
            "TWCAT252_16-DIESEL",
        ],
        "cc_min": 1600,
        "cc_max": 2200,
        "fuel": "DIESEL",
    },
    {
        "match": [
            "TWCAT002 DIESEL",
            "TWCAT002 DIESEL OVALADO 2 PULGADAS",
            "DIESELTWCAT002OVALADO2PULGADAS",
        ],
        "cc_min": 800,
        "cc_max": 1800,
        "fuel": "DIESEL",
    },
    # GASOLINA / BENCINA
    {"match": ["CLF016"], "cc_min": 1600, "cc_max": 2200, "fuel": "BENCINA"},
    {"match": ["CLF012", "CAT12"], "cc_min": 1600, "cc_max": 2200, "fuel": "BENCINA"},
    {"match": ["CAT18"], "cc_min": 800, "cc_max": 1600, "fuel": "BENCINA"},
    {"match": ["CAT10.7", "CAT107"], "cc_min": 800, "cc_max": 1600, "fuel": "BENCINA"},
    {"match": ["CAT00225", "CAT225"], "cc_min": 800, "cc_max": 1800, "fuel": "BENCINA"},
    {"match": ["CAT002250", "CAT250"], "cc_min": 800, "cc_max": 1800, "fuel": "BENCINA"},
    {"match": ["CAT002"], "cc_min": 800, "cc_max": 1800, "fuel": "BENCINA"},
    {"match": ["TWCAT051"], "cc_min": 2200, "cc_max": 3800, "fuel": "BENCINA"},
    {"match": ["TWCAT237250"], "cc_min": 2200, "cc_max": 3800, "fuel": "BENCINA"},
    {"match": ["TWCAT003200"], "cc_min": 1600, "cc_max": 2200, "fuel": "BENCINA"},
    {"match": ["TWCAT242"], "cc_min": 800, "cc_max": 1800, "fuel": "BENCINA"},
]


class Command(BaseCommand):
    help = (
        "Rellena recommended_cc_min, recommended_cc_max y combustible en productos "
        "catalíticos según reglas por SKU/nombre. Reglas específicas van antes que genéricas."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se actualizaría, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        # Productos de categorías catalíticas (y cualquier otro con sku/nombre que coincida)
        cataliticos_slugs = (
            "cataliticos",
            "cataliticos-twc",
            "cataliticos-twc-euro3",
            "cataliticos-twc-euro4",
            "cataliticos-twc-euro5",
            "cataliticos-twc-diesel",
            "cataliticos-clf",
            "cataliticos-ensamble-directo",
        )
        qs = (
            Product.objects.filter(
                deleted_at__isnull=True,
                category__slug__in=cataliticos_slugs,
            )
            .select_related("category")
            .order_by("id")
        )

        updated = 0
        for product in qs:
            combined = _norm(product.sku) + _norm(product.name)
            for rule in RULES:
                for m in rule["match"]:
                    if _norm(m) in combined:
                        cc_min = rule["cc_min"]
                        cc_max = rule["cc_max"]
                        fuel = rule["fuel"]
                        if dry_run:
                            self.stdout.write(
                                f"  [DRY-RUN] id={product.id} {product.sku} -> "
                                f"cc_min={cc_min} cc_max={cc_max} fuel={fuel}"
                            )
                        else:
                            update_fields = []
                            if product.recommended_cc_min != cc_min:
                                product.recommended_cc_min = cc_min
                                update_fields.append("recommended_cc_min")
                            if product.recommended_cc_max != cc_max:
                                product.recommended_cc_max = cc_max
                                update_fields.append("recommended_cc_max")
                            if product.combustible != fuel:
                                product.combustible = fuel
                                update_fields.append("combustible")
                            if update_fields:
                                product.save(update_fields=update_fields)
                                updated += 1
                                self.stdout.write(
                                    f"  id={product.id} {product.sku} -> "
                                    f"cc_min={cc_min} cc_max={cc_max} fuel={fuel}"
                                )
                        break
                else:
                    continue
                break

        self.stdout.write(
            self.style.SUCCESS(f"Actualizados: {updated} productos." + (" (dry-run)" if dry_run else ""))
        )
