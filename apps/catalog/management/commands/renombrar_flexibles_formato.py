# -*- coding: utf-8 -*-
"""
Actualiza los nombres de todos los productos flexibles al formato:
  Flexible Reforzado 1,75" x 8"
  Flexible Reforzado con extensión 2" x 6"

Respeta las medidas de cada SKU (diámetro x largo en pulgadas).
Usa coma para decimales y comillas para pulgadas.

Uso:
  python manage.py renombrar_flexibles_formato
  python manage.py renombrar_flexibles_formato --dry-run
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import parse_flexible_measure_from_sku



def _format_measure(val):
    """Formatea diámetro o largo: 1.75 -> '1,75', 2 -> '2', 2.5 -> '2,5'."""
    if val is None:
        return ""
    v = float(val)
    if v == int(v):
        return str(int(v))
    return str(v).replace(".", ",")


def _build_flexible_name(sku, parsed, con_extension=False):
    """
    Construye el nombre en formato: Flexible Reforzado {d}" x {l}"
    o Flexible Reforzado con extensión {d}" x {l}"
    """
    if not parsed:
        return None
    diam, largo = parsed
    d_str = _format_measure(diam)
    l_str = _format_measure(largo)
    base = "Flexible Reforzado"
    if con_extension:
        base += " con extensión"
    return f'{base} {d_str}" x {l_str}"'


class Command(BaseCommand):
    help = 'Actualiza nombres de flexibles al formato "Flexible Reforzado 1,75" x 8"" respetando medidas del SKU.'

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué nombres se cambiarían, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        cat_root = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat_root:
            cat_root = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat_root:
            self.stderr.write(self.style.ERROR("No existe la categoría Flexibles."))
            return

        cat_ids = [cat_root.id] + list(
            Category.objects.filter(parent=cat_root, is_active=True).values_list("id", flat=True)
        )

        products = Product.objects.filter(category_id__in=cat_ids, deleted_at__isnull=True).order_by("sku")
        updated = 0
        skipped = 0

        for prod in products:
            sku = (prod.sku or "").strip()
            parsed = parse_flexible_measure_from_sku(sku)
            con_extension = "EXT" in (sku or "").upper() or "ext" in (sku or "").lower()

            new_name = _build_flexible_name(sku, parsed, con_extension=con_extension)
            if not new_name:
                self.stdout.write(self.style.WARNING(f"  [SALTAR] {prod.sku}: no se pudo parsear medida"))
                skipped += 1
                continue

            new_name = new_name[:255]
            if prod.name != new_name:
                self.stdout.write(f"  {prod.sku}: \"{prod.name}\" -> \"{new_name}\"")
                if not dry_run:
                    prod.name = new_name
                    prod.save(update_fields=["name"])
                updated += 1

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Dry-run: {updated} productos actualizarían nombre." + (f" {skipped} omitidos (SKU sin medida)." if skipped else ""))
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Listo: {updated} flexibles con nombre actualizado." + (f" {skipped} omitidos." if skipped else ""))
            )
