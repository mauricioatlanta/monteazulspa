# -*- coding: utf-8 -*-
"""
Añade productos indicados en la nota manuscrita:
- Flexibles: 170x10, 2x4, 2x10, 3x4
- TWCAT: TWCAT052-22-10.7 Euro 3, TWCAT056-16 Euro 5
- Diesel: TW3221D, TWCAT002 D (si no existen)

Uso: python manage.py add_productos_nota [--dry-run]
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import (
    get_display_name_for_sku,
    normalize_measure_to_sku,
)
from apps.catalog.management.commands.sync_flexibles_precios import (
    FLEXIBLES_REFORZADOS,
    FLEXIBLES_SUFFIX,
    _get_or_create_category,
)

# 170x10 en nota = 1.75X10 en formato catálogo (1.75" x 10")
FLEXIBLES_NOTA = {
    "170X10": 14000,  # = 1.75X10
    "1.75X10": 14000,
    "2X4": 10000,
    "2X10": 13000,
    "3X4": 28000,
}

# TWCAT de la nota: (sku, nombre, subcategoria, precio, diam_pulg, euro_norm)
TWCAT_NOTA = [
    ("TWCAT052-22-10.7", "Catalítico TWCAT052-22-10.7 Redondo", "cataliticos-twc-euro3", 45000, 2, "EURO3"),
    ("TWCAT056-16", "Catalítico TWCAT056-16 Redondo", "cataliticos-twc-euro5", 148000, 2, "EURO5"),
]

# Diesel (SKU canónico; se crean si faltan)
DIESEL_NOTA = [
    ("TW3221D DIESEL", "Catalítico TW3221D Diesel Redondo", "cataliticos-twc-diesel", 60000, 2),
    ("TWCAT002 DIESEL", "Catalítico TWCAT002 Diesel Ovalado", "cataliticos-twc-diesel", 60000, 2),
]


def _ensure_flexible(sku, price, cat_normales, dry_run, stdout, style):
    """Crea o actualiza flexible; devuelve (created, updated)."""
    sku_norm = normalize_measure_to_sku(sku)
    if not sku_norm:
        sku_norm = sku.upper().replace(" ", "").replace("x", "X")
    # 170X10 → 1.75X10 para nombre
    display_sku = "1.75X10" if sku_norm == "170X10" else sku_norm
    name = get_display_name_for_sku(display_sku, include_suffix=True, suffix=FLEXIBLES_SUFFIX)
    if not name:
        name = f"{display_sku.replace('X', ' x ')} Reforzado"[:255]
    prod = Product.objects.filter(sku__iexact=sku).first()
    if not prod and sku_norm != sku:
        prod = Product.objects.filter(sku__iexact=sku_norm).first()
    if not prod:
        for p in Product.objects.filter(sku__icontains="X").exclude(sku__icontains="EXT"):
            if normalize_measure_to_sku(p.sku) == sku_norm or normalize_measure_to_sku(p.sku) == "1.75X10" and sku_norm == "170X10":
                prod = p
                break
    if prod:
        changed = False
        if prod.price != Decimal(str(price)):
            prod.price = Decimal(str(price))
            changed = True
        if prod.category_id != cat_normales.id:
            prod.category = cat_normales
            changed = True
        if changed and not dry_run:
            prod.save(update_fields=["price", "category"])
        return (0, 1 if changed else 0)
    if not dry_run:
        slug_base = slugify(sku_norm)[:280]
        slug = slug_base
        cnt = 0
        while Product.objects.filter(slug=slug).exists():
            cnt += 1
            slug = f"{slug_base}-{cnt}"[:280]
        Product.objects.create(
            sku=sku_norm,
            name=name[:255],
            slug=slug,
            category=cat_normales,
            price=Decimal(str(price)),
            cost_price=Decimal("0"),
            stock=0,
            is_active=True,
            is_publishable=True,
        )
    stdout.write(style.SUCCESS(f"  Flexible {sku_norm}: creado - {name} ${price}"))
    return (1, 0)


def _ensure_twcat(sku, name, subcat_slug, price, diam, euro_norm, dry_run, stdout, style):
    """Crea o actualiza catalítico TWCAT. Retorna (created, updated)."""
    cat = Category.objects.filter(slug=subcat_slug, is_active=True).first()
    if not cat:
        return (0, 0)
    prod = Product.objects.filter(sku__iexact=sku).first()
    if prod:
        changed = False
        if prod.category_id != cat.id:
            prod.category = cat
            changed = True
        if prod.price != Decimal(str(price)):
            prod.price = Decimal(str(price))
            changed = True
        if not prod.diametro_entrada or float(prod.diametro_entrada) != diam:
            prod.diametro_entrada = Decimal(str(diam))
            prod.diametro_salida = Decimal(str(diam))
            changed = True
        if euro_norm and prod.euro_norm != euro_norm:
            prod.euro_norm = euro_norm
            changed = True
        if prod.combustible != "BENCINA":
            prod.combustible = "BENCINA"
            changed = True
        if changed and not dry_run:
            prod.save()
        return (0, 1 if changed else 0)
    if not dry_run:
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
            category=cat,
            price=Decimal(str(price)),
            cost_price=Decimal("0"),
            stock=0,
            diametro_entrada=Decimal(str(diam)),
            diametro_salida=Decimal(str(diam)),
            euro_norm=euro_norm,
            combustible="BENCINA",
            is_active=True,
        )
    stdout.write(style.SUCCESS(f"  {sku}: creado -> {subcat_slug} | ${price}"))
    return (1, 0)


def _ensure_diesel(sku, name, subcat_slug, price, diam, dry_run, stdout, style):
    """Crea o actualiza catalítico diesel. Retorna (created, updated)."""
    cat = Category.objects.filter(slug=subcat_slug, is_active=True).first()
    if not cat:
        return (0, 0)
    prod = Product.objects.filter(sku__iexact=sku).first()
    if not prod:
        variants = [sku.replace(" ", ""), sku.replace(" DIESEL", " D"), "TW3221D", "TWCAT002 D"]
        for v in variants:
            prod = Product.objects.filter(sku__iexact=v).first()
            if prod:
                break
    if prod:
        changed = False
        if prod.category_id != cat.id:
            prod.category = cat
            changed = True
        if prod.price != Decimal(str(price)):
            prod.price = Decimal(str(price))
            changed = True
        if not prod.diametro_entrada or float(prod.diametro_entrada) != diam:
            prod.diametro_entrada = Decimal(str(diam))
            prod.diametro_salida = Decimal(str(diam))
            changed = True
        if prod.combustible != "DIESEL":
            prod.combustible = "DIESEL"
            changed = True
        if changed and not dry_run:
            prod.save()
        return (0, 1 if changed else 0)
    if not dry_run:
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
            category=cat,
            price=Decimal(str(price)),
            cost_price=Decimal("0"),
            stock=0,
            diametro_entrada=Decimal(str(diam)),
            diametro_salida=Decimal(str(diam)),
            combustible="DIESEL",
            is_active=True,
        )
    stdout.write(style.SUCCESS(f"  {sku}: creado -> {subcat_slug} | ${price}"))
    return (1, 0)


class Command(BaseCommand):
    help = "Añade productos de la nota: flexibles, TWCAT, diesel."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar, no guardar.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        created = 0
        updated = 0

        # Flexibles
        cat_flex = Category.objects.filter(slug="flexibles", is_active=True).first() or Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat_flex:
            self.stderr.write(self.style.ERROR("No existe categoría Flexibles."))
        else:
            cat_normales = _get_or_create_category("flexibles-normales", "Flexibles estándar", cat_flex)
            self.stdout.write("")
            self.stdout.write("FLEXIBLES (nota):")
            for sku in ["170X10", "2X4", "2X10", "3X4"]:
                price = FLEXIBLES_NOTA.get(sku) or FLEXIBLES_REFORZADOS.get(sku) or FLEXIBLES_REFORZADOS.get("1.75X10" if sku == "170X10" else sku)
                if price:
                    c, u = _ensure_flexible(sku, price, cat_normales, dry_run, self.stdout, self.style)
                    created += c
                    updated += u

        # TWCAT Euro 3 / Euro 5
        self.stdout.write("")
        self.stdout.write("TWCAT (nota):")
        for sku, name, subcat, price, diam, euro in TWCAT_NOTA:
            c, u = _ensure_twcat(sku, name, subcat, price, diam, euro, dry_run, self.stdout, self.style)
            created += c
            updated += u

        # Diesel
        self.stdout.write("")
        self.stdout.write("DIESEL (nota):")
        for sku, name, subcat, price, diam in DIESEL_NOTA:
            c, u = _ensure_diesel(sku, name, subcat, price, diam, dry_run, self.stdout, self.style)
            created += c
            updated += u

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Listo: {created} creados, {updated} actualizados." + (" (dry-run)" if dry_run else "")))
        if dry_run:
            self.stdout.write(self.style.NOTICE("Ejecuta sin --dry-run para aplicar."))
