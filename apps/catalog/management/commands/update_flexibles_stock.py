# -*- coding: utf-8 -*-
"""
Actualiza el stock de los productos flexibles según la planilla "IMPORTACION CATALITICOS NUEVOS MARCA CAT".
Las medidas (fila 2) se normalizan a SKU (coma→punto, X mayúscula); la fila STOCK (fila 3) tiene las cantidades.

Medidas y stock tomados de la planilla:
  1.5X4→165, 1.75X6→148, 1.75X8→231, 2X4→99, 2.5X6→176, 2X8→306, 2X10→540,
  2X10X1→21, 2.5X8→550, 3X4→141, 3X6→10, 3X8→125, 4X2→328, 4X6→47, 4X8→275,
  2X6X1→45, 2X8X1→1598

Uso:
  python manage.py update_flexibles_stock
  python manage.py update_flexibles_stock --dry-run
  python manage.py update_flexibles_stock --create-missing   # crea productos faltantes con precio 0
"""
import re
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import (
    get_display_name_for_sku,
    FLEXIBLES_INNER_BRAID_NOMENCLATURE,
)

# Datos de la planilla: medida normalizada (SKU) -> cantidad en stock
# Modelos según lista de precios (FLEXIBLE PIPE WITH INNER BRAID + flex with napples).
# 1.75X12 incluido como modelo de la lista (stock 0 si no viene en planilla).
FLEXIBLES_MEDIDA_STOCK = {
    "1.75X6": 148,
    "1.75X8": 231,
    "1.75X12": 0,
    "2X4": 99,
    "2X6": 0,
    "2X8": 306,
    "2X10": 540,
    "2.5X6": 176,
    "2.5X8": 550,
    "3X6": 10,
    "3X8": 125,
    "4X6": 47,
    "4X8": 275,
}

FLEXIBLES_SUFFIX = " Reforzado"


def _normalize_measure_to_sku(val):
    """Convierte medida de planilla a SKU: coma→punto, espacios alrededor de X eliminados, X mayúscula."""
    if val is None or (isinstance(val, str) and not str(val).strip()):
        return ""
    s = str(val).strip().upper()
    s = s.replace(",", ".")
    s = re.sub(r"\s*[xX]\s*", "X", s)
    s = re.sub(r"\s+", "", s)[:50]
    return s


def _find_flexible_by_measure(category, measure_sku):
    """
    Busca un producto en Flexibles por SKU exacto o por variantes (ej. 4x2 -> 4X2).
    """
    for prod in Product.objects.filter(category=category, is_active=True):
        if (prod.sku or "").strip().upper() == measure_sku:
            return prod
        if _normalize_measure_to_sku(prod.sku) == measure_sku:
            return prod
    return None


class Command(BaseCommand):
    help = "Actualiza stock de flexibles según planilla IMPORTACION CATALITICOS (medidas y cantidades)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se actualizaría, sin guardar.",
        )
        parser.add_argument(
            "--create-missing",
            action="store_true",
            help="Crear productos faltantes en Flexibles (precio 0, nombre por medida).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        create_missing = options["create_missing"]

        # Preferir flexibles-normales (subcategoría); fallback a flexibles (raíz) para compatibilidad
        cat = Category.objects.filter(slug="flexibles-normales", is_active=True).first()
        if not cat:
            cat = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat:
            cat = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat:
            self.stderr.write(self.style.ERROR("No existe la categoría Flexibles."))
            return

        updated = 0
        created = 0
        not_found = []

        for measure_sku, stock in FLEXIBLES_MEDIDA_STOCK.items():
            prod = Product.objects.filter(
                category=cat, sku__iexact=measure_sku, is_active=True
            ).first()
            if not prod:
                prod = _find_flexible_by_measure(cat, measure_sku)
            if prod:
                if prod.stock != stock:
                    if not dry_run:
                        prod.stock = stock
                        prod.save(update_fields=["stock"])
                    self.stdout.write(
                        f"  {measure_sku}: stock {prod.stock} → {stock}"
                        + (" (dry-run)" if dry_run else "")
                    )
                    updated += 1
            else:
                if create_missing and not dry_run:
                    name = get_display_name_for_sku(measure_sku, include_suffix=True, suffix=FLEXIBLES_SUFFIX)
                    if not name:
                        name = f"Tubo flexible {measure_sku.replace('X', ' x ')}\""
                        if len(name) + len(FLEXIBLES_SUFFIX) <= 255:
                            name = name + FLEXIBLES_SUFFIX
                    name = (name or measure_sku)[:255]
                    slug_base = slugify(measure_sku)[:280]
                    slug = slug_base
                    cnt = 0
                    while Product.objects.filter(slug=slug).exists():
                        cnt += 1
                        slug = f"{slug_base}-{cnt}"[:280]
                    Product.objects.create(
                        sku=measure_sku,
                        name=name[:255],
                        slug=slug,
                        category=cat,
                        price=Decimal("0"),
                        cost_price=Decimal("0"),
                        stock=stock,
                        is_active=True,
                    )
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"  Creado: {measure_sku} stock={stock}"))
                else:
                    not_found.append(measure_sku)

        if not_found:
            self.stdout.write(
                self.style.WARNING(
                    f"Medidas sin producto en Flexibles ({len(not_found)}): {', '.join(not_found)}"
                )
            )
            if not create_missing:
                self.stdout.write(
                    self.style.NOTICE("  Usa --create-missing para crear los faltantes.")
                )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry-run: {updated} productos actualizarían stock; {len(not_found)} no encontrados."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Listo: {updated} flexibles actualizados, {created} creados; {len(not_found)} medidas sin producto."
                )
            )
