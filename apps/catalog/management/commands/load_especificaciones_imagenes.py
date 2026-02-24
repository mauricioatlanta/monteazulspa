# -*- coding: utf-8 -*-
"""
Actualiza productos del catálogo con peso y dimensiones (largo, ancho, alto en cm)
tomados de las especificaciones en imágenes: lista de precios flexibles/silenciadores
y planilla de catalíticos CAT (stock).

Fuentes:
- Imagen 1 (LIST PRICES): DWR/LTM flexibles – peso y dimensiones manuscritas.
- Imagen 2 (MONTEAZULSPA): Silenciadores LT/DW – peso y dimensiones por grupo.
- Imagen 3 (IMPORTACION CATALITICOS NUEVOS MARCA CAT): stock por código de dimensión (1.5X4, 2X6, etc.).

Uso:
  python manage.py load_especificaciones_imagenes
  python manage.py load_especificaciones_imagenes --dry-run
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.catalog.models import Product

# (sku, weight_kg, length_cm, width_cm, height_cm)
# Imagen 1: LIST PRICES (flexibles DWR / LTM)
SPECS_IMAGEN_1 = [
    ("DWR002", Decimal("3.95"), 55, 17, 17),
    ("DWR006", Decimal("4.55"), 62, 17, 17),
    ("DWR008", Decimal("5.85"), 62, 17, 17),
    ("DWR012", Decimal("6.5"), 78, 17, 17),
    ("LTM1259", Decimal("5.35"), 63, 25, 12),
    ("LTM1239", Decimal("5.9"), 55, 25, 12),
    ("LTM1256", Decimal("5.60"), 64, 24, 12),
]

# Imagen 2: MONTEAZULSPA (silenciadores LT / DW)
# Varios SKU comparten las mismas medidas por grupo
SPECS_IMAGEN_2 = [
    # LT040, LT041, LT042, LT043
    ("LT040", Decimal("3.95"), 52, 25, 12),
    ("LT041", Decimal("3.95"), 52, 25, 12),
    ("LT042", Decimal("3.95"), 52, 25, 12),
    ("LT043", Decimal("3.95"), 52, 25, 12),
    # LT2552, LT5400, LT541, LT542
    ("LT2552", Decimal("4.05"), 52, 25, 12),
    ("LT5400", Decimal("4.05"), 52, 25, 12),
    ("LT541", Decimal("4.05"), 52, 25, 12),
    ("LT542", Decimal("4.05"), 52, 25, 12),
    # DW002, DW004, DW008, DW016
    ("DW002", Decimal("4.65"), 54, 24, 12),
    ("DW004", Decimal("5"), 54, 24, 12),
    ("DW008", Decimal("5.85"), 63, 24, 12),
    ("DW016", Decimal("5.85"), 63, 24, 12),
]

# Imagen 3: IMPORTACION CATALITICOS NUEVOS MARCA CAT – stock por código dimensión
# Código en hoja -> stock (fila STOCK)
STOCK_CAT_IMAGEN_3 = {
    "1.5X4": 165,
    "1.75X6": 148,
    "1,75X8": 231,
    "2X4": 99,
    "2.5x4": 176,
    "2X6": 306,
    "2X8": 540,
    "2X10": 21,
    "2X10X1": 176,
    "2.5X6": 550,
    "2.5X8": 141,
    "3X4": 10,
    "3X6": 125,
    "3X8": 328,
    "4x2": 47,
    "4X6": 275,
    "4X8": 45,
    "2X6X1": 1598,
    "2X8X1": 1983,
}


def _normalize_dim_code(code):
    """Para códigos tipo 1.5X4 / 1,75X8: unifica coma a punto y X a mayúscula."""
    if not code:
        return code
    s = str(code).strip().replace(",", ".").upper()
    return s


def _find_product(identifier):
    """Busca producto por SKU exacto (case insensitive) o SKU sin espacios/guiones."""
    if not identifier:
        return None
    id_upper = str(identifier).strip().upper()
    id_clean = "".join(c for c in id_upper if c.isalnum() or c in ".,X")

    for sku_val in (id_upper, id_clean, _normalize_dim_code(identifier)):
        if not sku_val:
            continue
        p = Product.objects.filter(sku__iexact=sku_val, is_active=True).first()
        if p:
            return p
    p = Product.objects.filter(name__icontains=identifier.strip(), is_active=True).first()
    if p:
        return p
    norm = _normalize_dim_code(identifier)
    if norm:
        p = Product.objects.filter(name__icontains=norm, is_active=True).first()
    return p


def _apply_specs(product, weight, length, width, height, dry_run):
    """Actualiza producto con peso y dimensiones. Devuelve True si hubo cambios."""
    updates = {}
    if weight is not None:
        updates["weight"] = weight
    if length is not None:
        updates["length"] = Decimal(str(length))
    if width is not None:
        updates["width"] = Decimal(str(width))
    if height is not None:
        updates["height"] = Decimal(str(height))
    if not updates:
        return False
    if dry_run:
        return True
    for key, value in updates.items():
        setattr(product, key, value)
    product.save(update_fields=list(updates.keys()))
    return True


def _apply_stock(product, stock, dry_run):
    """Actualiza stock del producto. Devuelve True si hubo cambio."""
    if stock is None:
        return False
    if dry_run:
        return True
    product.stock = int(stock)
    product.save(update_fields=["stock"])
    return True


class Command(BaseCommand):
    help = "Carga peso, dimensiones y (opcional) stock desde especificaciones de imágenes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se actualizaría, sin guardar.",
        )
        parser.add_argument(
            "--no-cat-stock",
            action="store_true",
            help="No actualizar stock de catalíticos CAT (imagen 3).",
        )

    def handle(self, dry_run, no_cat_stock, **options):
        updated_specs = 0
        updated_stock = 0
        not_found_specs = []
        not_found_stock = []

        # Imagen 1 + 2: peso y dimensiones
        all_specs = SPECS_IMAGEN_1 + SPECS_IMAGEN_2
        for sku, weight, length, width, height in all_specs:
            product = _find_product(sku)
            if not product:
                not_found_specs.append(sku)
                continue
            if _apply_specs(product, weight, length, width, height, dry_run):
                updated_specs += 1
                self.stdout.write(f"  {product.sku}: peso={weight} kg, largo={length}, ancho={width}, alto={height} cm")

        # Imagen 3: stock catalíticos CAT (por código de dimensión en nombre/SKU)
        if not no_cat_stock:
            for code, stock in STOCK_CAT_IMAGEN_3.items():
                product = _find_product(code)
                if not product:
                    not_found_stock.append(code)
                    continue
                if _apply_stock(product, stock, dry_run):
                    updated_stock += 1
                    self.stdout.write(f"  {product.sku}: stock={stock}")

        if not_found_specs:
            self.stdout.write(
                self.style.WARNING(f"SKU no encontrados (peso/dimensiones): {', '.join(not_found_specs)}")
            )
        if not_found_stock:
            self.stdout.write(
                self.style.WARNING(f"Códigos no encontrados (stock CAT): {', '.join(not_found_stock)}")
            )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY RUN: se actualizarían {updated_specs} productos con peso/dimensiones "
                    f"y {updated_stock} con stock. Ejecuta sin --dry-run para guardar."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Listo: {updated_specs} productos con peso/dimensiones, {updated_stock} con stock."
                )
            )
