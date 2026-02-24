# -*- coding: utf-8 -*-
"""
Actualiza solo los nombres de los productos flexibles al formato de la lista de precios
(FLEXIBLE PIPE WITH INNER BRAID: "1.75 X 6", "2.5 X 6", etc.; flex con nipple: "Flex reforzado con nipple 2 X 6").
No modifica precios.

Uso:
  python manage.py actualizar_nombres_flexibles
  python manage.py actualizar_nombres_flexibles --dry-run
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import (
    get_display_name_for_sku,
    FLEXIBLES_INNER_BRAID_NOMENCLATURE,
    FLEXIBLES_NIPPLES_NOMENCLATURE,
    normalize_measure_to_sku,
)

FLEXIBLES_SUFFIX = " Reforzado"


class Command(BaseCommand):
    help = "Actualiza nombres de productos en Flexibles a la nomenclatura de la lista de precios (sin tocar precios)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué nombres se cambiarían, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        cat = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat:
            cat = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat:
            self.stderr.write(self.style.ERROR("No existe la categoría Flexibles."))
            return

        # Incluir raíz y subcategorías (flexibles-normales, flexibles-con-extension)
        cat_ids = [cat.id] + list(
            Category.objects.filter(parent=cat, is_active=True).values_list("id", flat=True)
        )
        products = Product.objects.filter(category_id__in=cat_ids, is_active=True).order_by("sku")
        updated = 0

        for prod in products:
            sku = (prod.sku or "").strip()
            key = normalize_measure_to_sku(sku)
            sku_upper = sku.upper()

            if key in FLEXIBLES_INNER_BRAID_NOMENCLATURE:
                new_name = (FLEXIBLES_INNER_BRAID_NOMENCLATURE[key] + FLEXIBLES_SUFFIX)[:255]
            elif sku_upper in FLEXIBLES_NIPPLES_NOMENCLATURE:
                new_name = FLEXIBLES_NIPPLES_NOMENCLATURE[sku_upper][:255]
            else:
                continue

            if prod.name != new_name:
                self.stdout.write(f"  {prod.sku}: «{prod.name[:50]}...» → «{new_name[:50]}...»")
                if not dry_run:
                    prod.name = new_name
                    prod.save(update_fields=["name"])
                updated += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Dry-run: {updated} productos actualizarían nombre.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Listo: {updated} flexibles con nombre actualizado a la nomenclatura.")
            )
