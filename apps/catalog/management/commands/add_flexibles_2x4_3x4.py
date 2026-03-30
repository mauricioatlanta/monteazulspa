# -*- coding: utf-8 -*-
"""
Añade los flexibles sin extensión 2X4, 2X10 y 3X4 si no existen.
Usa el mismo criterio que sync_flexibles_precios: categoría flexibles-normales,
precios de la tabla oficial, nombre formato "Flexible Reforzado X" x Y"".

Uso: python manage.py add_flexibles_2x4_3x4 [--dry-run]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import normalize_measure_to_sku

# Mismo criterio que sync_flexibles_precios (crea si faltan)
FLEXIBLES_A_AGREGAR = {
    "2X4": 10000,
    "2X10": 13000,
    "3X4": 28000,
}


def _format_measure(val):
    """1.75 -> '1,75', 2 -> '2'."""
    if val is None:
        return ""
    v = float(val)
    if v == int(v):
        return str(int(v))
    return str(v).replace(".", ",")


def _build_name(sku):
    """Flexible Reforzado 2" x 4" etc."""
    from apps.catalog.flexibles_nomenclature import parse_flexible_measure_from_sku

    parsed = parse_flexible_measure_from_sku(sku)
    if not parsed:
        return None
    diam, largo = parsed
    d_str = _format_measure(diam)
    l_str = _format_measure(largo)
    return f'Flexible Reforzado {d_str}" x {l_str}"'


class Command(BaseCommand):
    help = "Añade flexibles sin extensión 2X4, 2X10 y 3X4 al catálogo (mismo criterio que los demás)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        qs = Product._meta.model._base_manager
        cat_flex = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat_flex:
            cat_flex = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat_flex:
            self.stderr.write(self.style.ERROR("No existe la categoría Flexibles."))
            return

        cat_normales, _ = Category.objects.get_or_create(
            slug="flexibles-normales",
            defaults={"name": "Flexibles estándar", "parent": cat_flex, "is_active": True},
        )
        if cat_normales.parent_id != cat_flex.id and not dry_run:
            cat_normales.parent = cat_flex
            cat_normales.save(update_fields=["parent"])

        created = 0
        for sku, price in FLEXIBLES_A_AGREGAR.items():
            sku_norm = normalize_measure_to_sku(sku)
            prod = qs.filter(sku__iexact=sku).first()
            if not prod and sku_norm:
                cat_ids = [cat_flex.id] + list(
                    Category.objects.filter(parent=cat_flex, is_active=True).values_list("id", flat=True)
                )
                for p in qs.filter(category_id__in=cat_ids).filter(sku__icontains="X").exclude(sku__icontains="EXT"):
                    if normalize_measure_to_sku(p.sku) == sku_norm:
                        prod = p
                        break
            if prod:
                self.stdout.write(f"  {sku}: ya existe (SKU {prod.sku})")
                continue

            name = _build_name(sku)
            if not name:
                name = f"{sku.replace('X', ' x ')} Reforzado"[:255]
            else:
                name = name[:255]
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"  [DRY-RUN] Crearía {sku}: {name} ${price}"))
                created += 1
                continue

            slug_base = slugify(sku)[:280]
            slug = slug_base
            cnt = 0
            while Product.objects.filter(slug=slug).exists():
                cnt += 1
                slug = f"{slug_base}-{cnt}"[:280]
            Product.objects.create(
                sku=sku,
                name=name[:255],
                slug=slug,
                category=cat_normales,
                price=Decimal(str(price)),
                cost_price=Decimal("0"),
                stock=0,
                is_active=True,
                is_publishable=True,
            )
            self.stdout.write(self.style.SUCCESS(f"  {sku}: creado - {name} ${price}"))
            created += 1

        if dry_run:
            self.stdout.write(self.style.NOTICE(f"Dry-run: {created} productos se crearían."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Listo: {created} flexibles añadidos."))
