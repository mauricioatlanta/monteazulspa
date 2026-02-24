# -*- coding: utf-8 -*-
"""
Ajustes de catálogo según observaciones del cliente (MonteazulSPA).

FASE 1 — EURO 3: Verificar productos sin imagen, ocultar si no tienen.
FASE 2 — EURO 5: Eliminar productos indicados, reordenar TWCAT052-16 primero.
FASE 3 — REDONDOS: LT043 — reemplazo de imagen (usar set_product_image con --image).
FASE 4 — FLEXIBLES: Revisar medidas 12x10, 2x4, 2x10, 3x8; normalizar nombres.
FASE 5 — MTT: Bloque agregado en template product_detail.html (no en este comando).

Uso:
  python manage.py ajustes_catalogo_cliente [--dry-run] [--phase 1|2|3|4|all]
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Product, ProductImage, Category
from apps.catalog.flexibles_nomenclature import (
    normalize_measure_to_sku,
    parse_flexible_measure_from_sku,
    get_display_name_for_sku,
    FLEXIBLES_INNER_BRAID_NOMENCLATURE,
)

# Categoría Euro 5 (slug canónico)
EURO5_CAT_SLUG = "cataliticos-twc-euro5"

# SKU que debe aparecer primero en Euro 5
EURO5_FIRST_SKU = "TWCAT052-16"

# Productos Euro 5 a eliminar (soft delete): SKU o patrones
# TWCAT056-16 (Redondo), TWCAT002 Ovalado Diesel (segundo), TWCAT052 Redondo 18cm
PRODUCTS_TO_REMOVE_EURO5 = [
    "TWCAT056-16",           # Redondo
    "TWCAT052-18",           # Redondo 18cm (si existe)
]
# TWCAT002 Ovalado Diesel: hay que identificar el "segundo" - por id o nombre

# Productos Euro 3 a verificar imagen
EURO3_SKUS_CHECK = ["TWCAT052-10.7", "TWCAT052-10,7", "TWCAT052-8"]

# Medidas flexibles a revisar (normalizadas)
FLEX_MEASURES = ["12X10", "2X4", "2X10", "3X8"]


def _has_image(product):
    """Verifica si el producto tiene imagen: ProductImage con archivo o carpeta media/products/<sku>/."""
    imgs = list(product.images.all())
    for img in imgs:
        if img.image and img.image.name:
            path = Path(settings.MEDIA_ROOT) / img.image.name
            if path.exists():
                return True
    # Carpeta por SKU
    sku_clean = str(product.sku).strip().replace(" ", "").replace(",", ".")
    media_products = Path(settings.MEDIA_ROOT) / "products"
    sku_dir = media_products / sku_clean
    if sku_dir.exists():
        for ext in (".webp", ".png", ".jpg", ".jpeg"):
            for f in sku_dir.glob(f"*{ext}"):
                if f.is_file():
                    return True
    return False


class Command(BaseCommand):
    help = "Ajustes de catálogo según observaciones del cliente (Euro 3, Euro 5, Flexibles)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se haría, sin modificar.",
        )
        parser.add_argument(
            "--phase",
            type=str,
            default="all",
            choices=["1", "2", "3", "4", "all"],
            help="Fase a ejecutar: 1=Euro3, 2=Euro5, 3=Redondos, 4=Flexibles, all=todas.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        phase = options["phase"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo DRY-RUN: no se modificará la base de datos."))

        if phase in ("1", "all"):
            self._phase1_euro3(dry_run)
        if phase in ("2", "all"):
            self._phase2_euro5(dry_run)
        if phase in ("3", "all"):
            self._phase3_redondos(dry_run)
        if phase in ("4", "all"):
            self._phase4_flexibles(dry_run)

    def _phase1_euro3(self, dry_run):
        """FASE 1: Verificar productos Euro 3 sin imagen; ocultar si no tienen."""
        self.stdout.write("\n--- FASE 1: Euro 3 - Productos sin imagen ---")
        for sku_variant in EURO3_SKUS_CHECK:
            prods = list(Product.objects.filter(sku__iexact=sku_variant))
            for p in prods:
                has_img = _has_image(p)
                if not has_img:
                    self.stdout.write(
                        self.style.WARNING(f"[SIN IMAGEN] {p.sku} - {p.name} (cat: {p.category.slug if p.category_id else '-'})")
                    )
                    if not dry_run and p.is_active:
                        p.is_active = False
                        p.save(update_fields=["is_active"])
                        self.stdout.write(self.style.SUCCESS(f"  → Ocultado (is_active=False)"))
                else:
                    self.stdout.write(f"[OK] {p.sku} tiene imagen")

    def _phase2_euro5(self, dry_run):
        """FASE 2: Eliminar productos indicados, asegurar orden TWCAT052-16 primero."""
        self.stdout.write("\n--- FASE 2: Euro 5 - Eliminar productos y reordenar ---")
        try:
            cat_euro5 = Category.objects.get(slug=EURO5_CAT_SLUG, is_active=True)
        except Category.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Categoría {EURO5_CAT_SLUG} no encontrada."))
            return

        # Eliminar por SKU exacto
        for sku in PRODUCTS_TO_REMOVE_EURO5:
            prods = list(Product.objects.filter(sku__iexact=sku, category=cat_euro5))
            for p in prods:
                self.stdout.write(f"[ELIMINAR] {p.sku} - {p.name}")
                if not dry_run:
                    p.soft_delete()
                    self.stdout.write(self.style.SUCCESS(f"  → Soft delete aplicado"))

        # TWCAT002 Ovalado Diesel (el segundo): buscar por nombre "Ovalado" y "Diesel"
        twcat002_ovalado = list(
            Product.objects.filter(
                category=cat_euro5,
                sku__icontains="TWCAT002",
                name__icontains="Ovalado",
                is_active=True,
                deleted_at__isnull=True,
            ).order_by("id")
        )
        # El "segundo" = el de abajo en lista ordenada por id
        if len(twcat002_ovalado) >= 2:
            to_remove = twcat002_ovalado[1]
            self.stdout.write(f"[ELIMINAR] TWCAT002 Ovalado Diesel (2º): {to_remove.sku} - {to_remove.name}")
            if not dry_run:
                to_remove.soft_delete()
                self.stdout.write(self.style.SUCCESS(f"  → Soft delete aplicado"))

        # TWCAT052 Redondo 18cm: buscar por nombre o largo
        twcat052_18 = list(
            Product.objects.filter(
                category=cat_euro5,
                sku__icontains="TWCAT052",
                name__icontains="18",
                is_active=True,
                deleted_at__isnull=True,
            )
        )
        for p in twcat052_18:
            if "18" in (p.name or "") and "redondo" in (p.name or "").lower():
                self.stdout.write(f"[ELIMINAR] TWCAT052 Redondo 18cm: {p.sku} - {p.name}")
                if not dry_run:
                    p.soft_delete()
                    self.stdout.write(self.style.SUCCESS(f"  → Soft delete aplicado"))

        self.stdout.write(self.style.SUCCESS("Fase 2 completada. Orden TWCAT052-16 primero se aplica en la vista (product_list)."))

    def _phase3_redondos(self, dry_run):
        """FASE 3: LT043 - Reemplazo de imagen. Instrucciones para ejecutar manualmente."""
        self.stdout.write("\n--- FASE 3: Redondos - LT043 ---")
        try:
            p = Product.objects.get(sku__iexact="LT043", is_active=True)
            self.stdout.write(f"Producto encontrado: {p.sku} - {p.name}")
            self.stdout.write(
                self.style.WARNING(
                    "Para reemplazar la imagen por la versión con dibujo de 5 formas, ejecute:\n"
                    "  python manage.py set_product_image LT043 --image /ruta/a/lt043_5formas.png"
                )
            )
        except Product.DoesNotExist:
            self.stdout.write(self.style.WARNING("Producto LT043 no encontrado."))

    def _phase4_flexibles(self, dry_run):
        """FASE 4: Revisar medidas flexibles 12x10, 2x4, 2x10, 3x8; normalizar nombres."""
        self.stdout.write("\n--- FASE 4: Flexibles - Revisar medidas ---")
        flex_cat_ids = list(
            Category.objects.filter(
                slug__in=("flexibles", "flexibles-reforzados", "flexibles-normales", "flexibles-con-extension"),
                is_active=True,
            ).values_list("id", flat=True)
        )
        if not flex_cat_ids:
            self.stdout.write(self.style.WARNING("No se encontraron categorías de flexibles."))
            return

        for meas in FLEX_MEASURES:
            key = normalize_measure_to_sku(meas)
            prods = list(
                Product.objects.filter(
                    category_id__in=flex_cat_ids,
                    sku__icontains=meas.replace("X", "x").replace("x", "X"),
                    is_active=True,
                    deleted_at__isnull=True,
                )
            )
            # Buscar también por SKU normalizado
            if not prods:
                prods = list(
                    Product.objects.filter(
                        category_id__in=flex_cat_ids,
                        is_active=True,
                        deleted_at__isnull=True,
                    )
                )
                prods = [p for p in prods if normalize_measure_to_sku(p.sku) == key]
            for p in prods:
                parsed = parse_flexible_measure_from_sku(p.sku)
                diam_str = str(parsed[0]) if parsed else "-"
                largo_str = str(parsed[1]) if parsed else "-"
                # Usar nomenclatura por medida (key), no por p.sku, para evitar "2X10P" → "Flexible Reforzado 2X10P"
                # Solo aplicar si las dimensiones parseadas coinciden con la medida que revisamos
                expected_name = None
                if key in FLEXIBLES_INNER_BRAID_NOMENCLATURE:
                    if parsed:
                        # Verificar que dimensiones coincidan (ej: 2X10P → 2x10, key 2X10)
                        d = int(parsed[0]) if parsed[0] == int(parsed[0]) else parsed[0]
                        l = int(parsed[1]) if parsed[1] == int(parsed[1]) else parsed[1]
                        norm_meas = normalize_measure_to_sku(f"{d}X{l}")
                        if norm_meas == key:
                            expected_name = "Flexible Reforzado " + FLEXIBLES_INNER_BRAID_NOMENCLATURE[key]
                    # SKU exacto en nomenclatura: usar display name si existe
                    sku_norm = normalize_measure_to_sku(p.sku or "")
                    if sku_norm == key:
                        disp = get_display_name_for_sku(p.sku, include_suffix=True)
                        if disp:
                            expected_name = "Flexible Reforzado " + disp.replace(" Reforzado", "").strip()
                ok = "OK" if "reforz" in (p.name or "").lower() or "flexible" in (p.name or "").lower() else "REVISAR"
                self.stdout.write(f"  {p.sku}: diam={diam_str} largo={largo_str} | nombre actual: {p.name} | {ok}")
                if expected_name and p.name != expected_name and not dry_run:
                    p.name = expected_name
                    p.save(update_fields=["name"])
                    self.stdout.write(self.style.SUCCESS(f"    → Nombre actualizado a: {expected_name}"))

        # Duplicados por SKU normalizado
        all_flex = Product.objects.filter(
            category_id__in=flex_cat_ids,
            is_active=True,
            deleted_at__isnull=True,
        )
        seen = {}
        for p in all_flex:
            k = normalize_measure_to_sku(p.sku or "")
            if not k:
                continue
            if k in seen:
                self.stdout.write(self.style.WARNING(f"  DUPLICADO: {p.sku} (misma medida que {seen[k].sku})"))
            else:
                seen[k] = p
