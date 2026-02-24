# -*- coding: utf-8 -*-
"""
Corrige convertidores catalíticos TWCAT según la lista oficial:
- Mueve productos a subcategorías correctas (Euro 3, Euro 4, Euro 5, Diesel)
- Completa diametro_entrada y diametro_salida (pulgadas)
- Actualiza precios
- Crea productos faltantes cuando el mismo modelo existe en varias subcategorías

Uso: python manage.py fix_twcat_catalog [--dry-run]
"""
import re
from decimal import Decimal

from django.db.models import Q
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product


# Lista oficial: (codigo, modelo, pulgadas, precio, subcategoria)
# SKUs que aparecen en varias subcategorías requieren productos separados
EXPECTED_TWCAT = [
    ("TWCAT0002-200", "ovalado", 2, 45000, "cataliticos-twc-euro3"),
    ("TWCAT0002-225", "ovalado", 2.25, 45000, "cataliticos-twc-euro3"),
    ("TWCAT002-250", "ovalado", 2.5, 50000, "cataliticos-twc-euro3"),
    ("TWCAT003", "redondo", 2, 37000, "cataliticos-twc-euro3"),
    ("TWCAT052-18", "redondo", 2, 45000, "cataliticos-twc-euro3"),
    ("TWCAT052-16", "redondo", 2, 45000, "cataliticos-twc-euro3"),
    ("TWCAT052-11", "redondo", 2, 45000, "cataliticos-twc-euro3"),
    ("TWCAT052-22", "redondo", 2, 45000, "cataliticos-twc-euro3"),
    ("TWCAT091-250 SUPER", "ovalado", 2.5, 70000, "cataliticos-twc-euro3"),
    ("TWCAT237 SENSOR", "ovalado", 2.5, 70000, "cataliticos-twc-euro3"),
    ("TWCAT042", "ovalado", 2, 45000, "cataliticos-twc-euro3"),
    ("TWCAT052-10,7", "redondo", 2, 68000, "cataliticos-twc-euro4"),
    ("TWCAT052-12", "redondo", 2, 68000, "cataliticos-twc-euro4"),
    ("TWCAT052-16", "redondo", 2, 68000, "cataliticos-twc-euro4"),
    ("TWCAT052-10,7", "redondo", 2, 148000, "cataliticos-twc-euro5"),
    ("TWCAT052-12", "redondo", 2, 148000, "cataliticos-twc-euro5"),
    ("TWCAT052-16", "redondo", 2, 148000, "cataliticos-twc-euro5"),
    ("TW3221D DIESEL", "redondo", 2, 60000, "cataliticos-twc-diesel"),
    ("TWCAT016 DIESEL", "redondo", 2, 60000, "cataliticos-twc-diesel"),
    ("TWCAT002 DIESEL", "ovalado", 2, 60000, "cataliticos-twc-diesel"),
]


def _normalize_sku(sku):
    """Normaliza SKU para matching (TWCAT0002--200 → TWCAT0002-200)."""
    if not sku:
        return ""
    s = str(sku).strip().upper().replace(",", ".").replace(" ", "-").replace("_", "-")
    return re.sub(r"-+", "-", s).strip("-")


# Aliases: SKU en DB -> clave normalizada esperada (para matching con lista oficial)
# EURO4_TWCAT0252_200_10CMS = TWCAT052-10,7 Euro 4, etc.
SKU_ALIAS_TO_KEY = {
    "EURO4_TWCAT0252_200_10CMS": "TWCAT052-10.7",
    "EURO4_TWCAT0252_200_12CMS": "TWCAT052-12",
    "EURO4_TWCAT0252_200_16CMS": "TWCAT052-16",
}


def _find_product_by_sku_variant(products, target_sku_norm):
    """Encuentra producto cuya versión normalizada coincide con target."""
    for p in products:
        if _normalize_sku(p.sku) == target_sku_norm:
            return p
    return None


def _euro_from_subcat(slug):
    """Extrae EURO3/EURO4/EURO5 o None para diesel."""
    if "euro3" in slug:
        return "EURO3"
    if "euro4" in slug:
        return "EURO4"
    if "euro5" in slug:
        return "EURO5"
    return None


class Command(BaseCommand):
    help = "Corrige TWCAT: subcategorías, medidas y precios según lista oficial."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar cambios, no guardar.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        # Cargar categorías
        cats = {}
        for slug in ("cataliticos-twc-euro3", "cataliticos-twc-euro4", "cataliticos-twc-euro5", "cataliticos-twc-diesel"):
            c = Category.objects.filter(slug=slug, is_active=True).first()
            if not c:
                self.stderr.write(self.style.ERROR(f"Falta categoría {slug}. Ejecuta estructura_categorias_cataliticos."))
                return
            cats[slug] = c

        # Productos TWCAT en DB
        all_twcat = list(
            Product.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
            .filter(Q(sku__icontains="TWCAT") | Q(sku__icontains="TW3221"))
            .select_related("category")
        )

        # Índice: sku_norm -> [productos]
        db_by_norm = {}
        for p in all_twcat:
            k = _normalize_sku(p.sku)
            db_by_norm.setdefault(k, []).append(p)
            # Aliases: EURO4_TWCAT0252_200_10CMS → TWCAT052-10.7
            alias_key = SKU_ALIAS_TO_KEY.get(p.sku.upper().strip())
            if alias_key:
                db_by_norm.setdefault(alias_key, []).append(p)

        # Procesar cada entrada esperada; para duplicados (mismo base SKU en varias subcats)
        # la primera usa el producto existente, las demás crean productos nuevos con sufijo
        used_product_ids = set()  # IDs ya asignados a una entrada
        created = 0
        updated = 0
        missing_base = []

        for codigo, modelo, pulg, precio, subcat in EXPECTED_TWCAT:
            key = _normalize_sku(codigo)
            cat = cats[subcat]
            euro = _euro_from_subcat(subcat)
            combustible = "DIESEL" if "diesel" in subcat else "BENCINA"

            # ¿Tenemos un producto existente que coincida?
            candidates = db_by_norm.get(key, [])
            prod = None
            for c in candidates:
                if c.id not in used_product_ids:
                    prod = c
                    break

            if prod:
                used_product_ids.add(prod.id)
                # Actualizar
                changes = []
                if prod.category_id != cat.id:
                    changes.append("cat")
                    prod.category = cat
                if prod.price != Decimal(str(precio)):
                    changes.append("price")
                    prod.price = Decimal(str(precio))
                di = float(prod.diametro_entrada) if prod.diametro_entrada else None
                if di is None or abs(di - pulg) > 0.01:
                    changes.append("diam")
                    prod.diametro_entrada = Decimal(str(pulg))
                    prod.diametro_salida = Decimal(str(pulg))
                if euro and prod.euro_norm != euro:
                    changes.append("euro")
                    prod.euro_norm = euro
                if prod.combustible != combustible:
                    changes.append("combustible")
                    prod.combustible = combustible

                # Incluir forma (redondo/ovalado) en nombre si falta
                txt = f"{prod.name or ''} {prod.ficha_tecnica or ''}".lower()
                if modelo == "redondo" and "redond" not in txt:
                    prod.name = f"{prod.name or prod.sku} Redondo".strip()[:255]
                    changes.append("nombre+redondo")
                elif modelo == "ovalado" and "oval" not in txt:
                    prod.name = f"{prod.name or prod.sku} Ovalado".strip()[:255]
                    changes.append("nombre+ovalado")

                if changes:
                    self.stdout.write(f"  Actualizar {prod.sku} -> {subcat}: {', '.join(changes)}")
                    if not dry_run:
                        uf = ["category", "price", "diametro_entrada", "diametro_salida", "euro_norm", "combustible"]
                        if "nombre+redondo" in changes or "nombre+ovalado" in changes:
                            uf.append("name")
                        prod.save(update_fields=uf)
                        prod.refresh_quality(save=True)
                    updated += 1
            else:
                # Crear producto nuevo (para duplicados Euro 4/Euro 5)
                suffix_map = {
                    "cataliticos-twc-euro4": "EURO4",
                    "cataliticos-twc-euro5": "EURO5",
                }
                suffix = suffix_map.get(subcat, "")
                new_sku = f"{codigo}-{suffix}" if suffix else codigo
                if Product.objects.filter(sku=new_sku).exists():
                    self.stdout.write(self.style.NOTICE(f"  Ya existe {new_sku}, actualizar en lugar de crear."))
                    prod = Product.objects.get(sku=new_sku)
                    prod.category = cat
                    prod.price = Decimal(str(precio))
                    prod.diametro_entrada = Decimal(str(pulg))
                    prod.diametro_salida = Decimal(str(pulg))
                    prod.euro_norm = euro
                    prod.combustible = combustible
                    txt = f"{prod.name or ''} {prod.ficha_tecnica or ''}".lower()
                    if modelo == "redondo" and "redond" not in txt:
                        prod.name = f"{prod.name or prod.sku} Redondo".strip()[:255]
                    elif modelo == "ovalado" and "oval" not in txt:
                        prod.name = f"{prod.name or prod.sku} Ovalado".strip()[:255]
                    if not dry_run:
                        prod.save()
                        prod.refresh_quality(save=True)
                    updated += 1
                else:
                    base_name = f"Catalítico {codigo} {modelo.capitalize()}" if not codigo.upper().endswith("DIESEL") else f"Catalítico {codigo}"
                    slug_base = slugify(new_sku)[:280]
                    slug = slug_base
                    n = 0
                    while Product.objects.filter(slug=slug).exists():
                        n += 1
                        slug = f"{slug_base}-{n}"[:280]

                    self.stdout.write(f"  Crear {new_sku} -> {subcat} | ${precio} | {pulg}\"")
                    if not dry_run:
                        Product.objects.create(
                            sku=new_sku,
                            name=base_name,
                            slug=slug,
                            category=cat,
                            price=Decimal(str(precio)),
                            cost_price=Decimal("0"),
                            stock=0,
                            diametro_entrada=Decimal(str(pulg)),
                            diametro_salida=Decimal(str(pulg)),
                            euro_norm=euro,
                            combustible=combustible,
                            is_active=True,
                        )
                    created += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Resumen: {updated} actualizados, {created} creados." + (" (dry-run)" if dry_run else "")
            )
        )
        if dry_run:
            self.stdout.write("Ejecuta sin --dry-run para aplicar.")
