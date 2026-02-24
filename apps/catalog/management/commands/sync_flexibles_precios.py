# -*- coding: utf-8 -*-
"""
Sincroniza productos flexibles con la tabla de precios oficial.
- FLEXIBLES REFORZADOS: flexibles-normales
- FLEXIBLES REF C/CAÑO (con extensión): flexibles-con-extension

Crea los productos faltantes y actualiza precios para que coincidan con la tabla.
Uso: python manage.py sync_flexibles_precios [--dry-run]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.utils.text import slugify

from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import (
    get_display_name_for_sku,
    normalize_measure_to_sku,
    FLEXIBLES_INNER_BRAID_NOMENCLATURE,
    FLEXIBLES_NIPPLES_NOMENCLATURE,
)

FLEXIBLES_SUFFIX = " Reforzado"

# FLEXIBLES REFORZADOS (flexibles-normales): SKU -> precio CLP
FLEXIBLES_REFORZADOS = {
    "1.75X4": 11000,
    "1.75X6": 14000,
    "1.75X8": 14000,
    "1.75X10": 14000,
    "1.75X12": 14000,
    "2X4": 10000,
    "2X6": 13000,
    "2X8": 13000,
    "2X10": 13000,
    "2.5X6": 19500,
    "2.5X8": 21000,
    "3X4": 28000,
    "3X6": 28000,
    "3X8": 31000,
    "4X6": 35000,
    "4X8": 35000,
}

# FLEXIBLES REF C/CAÑO (con extensión): SKU -> precio CLP
FLEXIBLES_CON_EXTENSION = {
    "2X6EXT-REF": 13000,
    "2X8EXT-REF": 15000,
    "2.5X6EXT-REF": 20000,
}


def _get_or_create_category(slug, name, parent=None):
    cat, _ = Category.objects.get_or_create(
        slug=slug,
        defaults={"name": name, "parent": parent, "is_active": True},
    )
    return cat


class Command(BaseCommand):
    help = "Sincroniza flexibles reforzados y con extensión con la tabla de precios."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar cambios sin guardar.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        cat_flex = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat_flex:
            cat_flex = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat_flex:
            self.stderr.write(self.style.ERROR("No existe la categoría Flexibles."))
            return

        cat_normales = _get_or_create_category("flexibles-normales", "Flexibles estándar", cat_flex)
        if cat_normales.parent_id != cat_flex.id:
            if not dry_run:
                cat_normales.parent = cat_flex
                cat_normales.save(update_fields=["parent"])

        cat_ext = _get_or_create_category("flexibles-con-extension", "Flexibles con extensión", cat_flex)
        if cat_ext.parent_id != cat_flex.id:
            if not dry_run:
                cat_ext.parent = cat_flex
                cat_ext.save(update_fields=["parent"])

        created = 0
        updated = 0

        # FLEXIBLES REFORZADOS
        self.stdout.write("")
        self.stdout.write("FLEXIBLES REFORZADOS (flexibles-normales):")
        for sku, price in sorted(FLEXIBLES_REFORZADOS.items(), key=lambda x: (x[0].replace("X", " "),)):
            name = get_display_name_for_sku(sku, include_suffix=True, suffix=FLEXIBLES_SUFFIX)
            if not name:
                name = f"{sku.replace('X', ' x ')} Reforzado"[:255]
            sku_norm = normalize_measure_to_sku(sku)
            # Buscar por SKU exacto (incluyendo soft-deleted) o variantes normalizadas
            qs = Product._meta.model._base_manager
            prod = qs.filter(sku__iexact=sku).first()
            if not prod and sku_norm:
                for p in qs.filter(sku__icontains="X").exclude(sku__icontains="EXT"):
                    if normalize_measure_to_sku(p.sku) == sku_norm:
                        prod = p
                        break
            if prod:
                needs_save = []
                if prod.price != Decimal(str(price)):
                    prod.price = Decimal(str(price))
                    needs_save.append("price")
                    self.stdout.write(f"  {prod.sku}: precio {prod.price} -> {price}" + (" (actualizado)" if not dry_run else " (dry-run)"))
                    updated += 1
                if prod.category_id != cat_normales.id:
                    prod.category = cat_normales
                    needs_save.append("category")
                    if "price" not in needs_save:
                        updated += 1
                if prod.name != name[:255]:
                    prod.name = name[:255]
                    needs_save.append("name")
                if not prod.is_active:
                    prod.is_active = True
                    needs_save.append("is_active")
                if needs_save and not dry_run:
                    prod.save(update_fields=needs_save)
            else:
                if not dry_run:
                    slug_base = slugify(sku)[:280]
                    slug = slug_base
                    cnt = 0
                    while Product.objects.filter(slug=slug).exists():
                        cnt += 1
                        slug = f"{slug_base}-{cnt}"[:280]
                    try:
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
                    except IntegrityError:
                        # SKU existe; buscar por normalizado (incl. soft-deleted) y actualizar
                        prod = None
                        for p in qs.filter(sku__icontains="X").exclude(sku__icontains="EXT"):
                            if sku_norm and normalize_measure_to_sku(p.sku) == sku_norm:
                                prod = p
                                break
                        if prod:
                            prod.price = Decimal(str(price))
                            prod.category = cat_normales
                            prod.name = name[:255]
                            prod.is_active = True
                            prod.save(update_fields=["price", "category", "name", "is_active"])
                            self.stdout.write(self.style.WARNING(f"  {prod.sku}: actualizado (SKU existente con formato distinto)"))
                            updated += 1
                        else:
                            raise
                self.stdout.write(self.style.SUCCESS(f"  {sku}: creado - {name} ${price}"))
                created += 1

        # FLEXIBLES CON EXTENSIÓN (REF C/CAÑO)
        self.stdout.write("")
        self.stdout.write("FLEXIBLES REF C/CAÑO (con extensión):")
        qs_ext = Product._meta.model._base_manager
        for sku, price in FLEXIBLES_CON_EXTENSION.items():
            name = FLEXIBLES_NIPPLES_NOMENCLATURE.get(sku) or f"Flex reforzado con extensión {sku.replace('EXT-REF', '').replace('X', ' x ')}"[:255]
            prod = qs_ext.filter(sku__iexact=sku).first()
            if prod:
                changed = False
                if prod.price != Decimal(str(price)):
                    if not dry_run:
                        prod.price = Decimal(str(price))
                        prod.save(update_fields=["price"])
                    self.stdout.write(f"  {sku}: precio {prod.price} -> {price}" + (" (actualizado)" if not dry_run else " (dry-run)"))
                    changed = True
                if prod.category_id != cat_ext.id:
                    if not dry_run:
                        prod.category = cat_ext
                        prod.save(update_fields=["category"])
                    if not changed:
                        self.stdout.write(f"  {sku}: categoria -> flexibles-con-extension")
                    changed = True
                if prod.name != name:
                    if not dry_run:
                        prod.name = name[:255]
                        prod.save(update_fields=["name"])
                    changed = True
                if changed:
                    updated += 1
            else:
                if not dry_run:
                    slug_base = slugify(sku)[:280]
                    slug = slug_base
                    cnt = 0
                    while Product.objects.filter(slug=slug).exists():
                        cnt += 1
                        slug = f"{slug_base}-{cnt}"[:280]
                    try:
                        Product.objects.create(
                            sku=sku,
                            name=name[:255],
                            slug=slug,
                            category=cat_ext,
                            price=Decimal(str(price)),
                            cost_price=Decimal("0"),
                            stock=0,
                            is_active=True,
                            is_publishable=True,
                        )
                    except IntegrityError:
                        prod = qs_ext.filter(sku__iexact=sku).first()
                        if prod:
                            prod.price = Decimal(str(price))
                            prod.category = cat_ext
                            prod.name = name[:255]
                            prod.is_active = True
                            prod.save(update_fields=["price", "category", "name", "is_active"])
                            self.stdout.write(self.style.WARNING(f"  {prod.sku}: actualizado (existente)"))
                            updated += 1
                        else:
                            raise
                self.stdout.write(self.style.SUCCESS(f"  {sku}: creado - {name} ${price}"))
                created += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {created} creados, {updated} actualizados." + (" (dry-run)" if dry_run else "")
            )
        )
        if dry_run:
            self.stdout.write(self.style.NOTICE("Ejecuta sin --dry-run para aplicar cambios."))
