# -*- coding: utf-8 -*-
"""
Audita los convertidores catalíticos TWCAT del catálogo contra la lista oficial.

Compara:
- Inclusión en subcategorías correctas (Euro 3, Euro 4, Euro 5, Diesel)
- Precios
- Medidas (pulgadas)
- Modelos (ovalado/redondo)

Uso: python manage.py audit_twcat_catalog
"""
from decimal import Decimal

from django.db.models import Q
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product


# Lista esperada según la tabla oficial (imagen):
# codigo, modelo, pulgadas, precio, subcategoria
EXPECTED_TWCAT = [
    # CATALITICOS TW EURO 3
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
    # CATALITICOS TW EURO 4
    ("TWCAT052-10,7", "redondo", 2, 68000, "cataliticos-twc-euro4"),
    ("TWCAT052-12", "redondo", 2, 68000, "cataliticos-twc-euro4"),
    ("TWCAT052-16", "redondo", 2, 68000, "cataliticos-twc-euro4"),
    # CATALITICOS TW EURO 5 (mismos SKU que Euro 4 pero distinto precio)
    ("TWCAT052-10,7", "redondo", 2, 148000, "cataliticos-twc-euro5"),
    ("TWCAT052-12", "redondo", 2, 148000, "cataliticos-twc-euro5"),
    ("TWCAT052-16", "redondo", 2, 148000, "cataliticos-twc-euro5"),
    # DIESEL
    ("TW3221D DIESEL", "redondo", 2, 60000, "cataliticos-twc-diesel"),
    ("TWCAT016 DIESEL", "redondo", 2, 60000, "cataliticos-twc-diesel"),
    ("TWCAT002 DIESEL", "ovalado", 2, 60000, "cataliticos-twc-diesel"),
]


def _normalize_sku_for_match(sku):
    """Normaliza SKU para comparación (ej: TWCAT052-10,7, TWCAT0002--200)."""
    if not sku:
        return ""
    import re
    s = str(sku).strip().upper()
    s = s.replace(",", ".").replace(" ", "-").replace("_", "-")
    s = re.sub(r"-+", "-", s)  # múltiples guiones → uno solo
    return s


# Aliases: SKU en DB -> clave normalizada esperada (para matchear con lista oficial)
SKU_ALIAS_TO_KEY = {
    "EURO4_TWCAT0252_200_10CMS": "TWCAT052-10.7",
    "EURO4_TWCAT0252_200_12CMS": "TWCAT052-12",
    "EURO4_TWCAT0252_200_16CMS": "TWCAT052-16",
}


def _product_contains_shape(product, shape):
    """True si el producto indica la forma (ovalado/redondo) en nombre o ficha."""
    txt = f"{product.name or ''} {product.ficha_tecnica or ''}".lower()
    return ("oval" in txt and shape == "ovalado") or ("redond" in txt and shape == "redondo")


class Command(BaseCommand):
    help = "Audita TWCAT: subcategorías, precios, medidas y modelos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            action="store_true",
            help="Salida en CSV.",
        )

    def handle(self, *args, **options):
        out_csv = options.get("csv", False)

        # Productos TWCAT en DB (sku o sku_canonico empieza con TWCAT o TW3221)
        all_twcat = Product.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
        ).filter(
            Q(sku__icontains="TWCAT") | Q(sku__icontains="TW3221")
        ).select_related("category").order_by("sku")

        # Mapeo: sku normalizado -> producto (puede haber duplicados si mismo SKU en Euro 4 y Euro 5)
        db_by_sku = {}  # sku_norm -> [product]
        for p in all_twcat:
            key = _normalize_sku_for_match(p.sku)
            db_by_sku.setdefault(key, []).append(p)
            # Aliases: EURO4_TWCAT0252_200_10CMS → TWCAT052-10.7
            alias_key = SKU_ALIAS_TO_KEY.get(p.sku.upper().strip())
            if alias_key:
                db_by_sku.setdefault(alias_key, []).append(p)
            # Productos con sufijo -EURO4/-EURO5 también matchean la base (ej. TWCAT052-12-EURO5 → TWCAT052-12)
            for suffix in ("-EURO4", "-EURO5"):
                if key.endswith(suffix):
                    base = key[: -len(suffix)]
                    db_by_sku.setdefault(base, []).append(p)
                    break

        # Índice por subcategoría esperada
        expected_by_subcat = {}
        for row in EXPECTED_TWCAT:
            codigo, modelo, pulg, precio, subcat = row
            key = _normalize_sku_for_match(codigo)
            expected_by_subcat.setdefault(subcat, []).append((key, codigo, modelo, pulg, precio))

        # Salida
        lines = []
        missing = []
        wrong_cat = []
        wrong_price = []
        wrong_pulg = []
        wrong_modelo = []
        ok_list = []

        for subcat in ("cataliticos-twc-euro3", "cataliticos-twc-euro4", "cataliticos-twc-euro5", "cataliticos-twc-diesel"):
            cat = Category.objects.filter(slug=subcat, is_active=True).first()
            cat_name = cat.name if cat else subcat

            for key, codigo, modelo, pulg_expected, precio_expected in expected_by_subcat.get(subcat, []):
                prods = db_by_sku.get(key, [])

                # Mismo SKU puede estar en Euro 4 y Euro 5 (ej TWCAT052-10,7)
                prod = None
                for p in prods:
                    p_slug = p.category.slug if p.category else ""
                    if p_slug == subcat:
                        prod = p
                        break
                if not prod and prods:
                    prod = prods[0]  # tomar el primero para reportar

                if not prod:
                    missing.append((codigo, subcat, modelo, pulg_expected, precio_expected))
                    continue

                # Verificar categoría
                p_slug = prod.category.slug if prod.category else ""
                if p_slug != subcat:
                    wrong_cat.append((codigo, p_slug, subcat))

                # Verificar precio
                try:
                    p_price = int(float(prod.price)) if prod.price else 0
                except (TypeError, ValueError):
                    p_price = 0
                if p_price != precio_expected:
                    wrong_price.append((codigo, subcat, p_price, precio_expected))

                # Verificar pulgadas (diametro_entrada o diametro_salida)
                di = float(prod.diametro_entrada) if prod.diametro_entrada else None
                ds = float(prod.diametro_salida) if prod.diametro_salida else None
                pulg_db = di or ds
                if pulg_db is not None:
                    # Aceptar pequeña tolerancia
                    if abs(pulg_db - pulg_expected) > 0.1:
                        wrong_pulg.append((codigo, subcat, pulg_db, pulg_expected))
                else:
                    wrong_pulg.append((codigo, subcat, None, pulg_expected))

                # Verificar modelo (ovalado/redondo) - solo si hay discrepancia
                if not _product_contains_shape(prod, modelo):
                    wrong_modelo.append((codigo, subcat, prod.name or "", modelo))

                if p_slug == subcat and p_price == precio_expected and (pulg_db is None or abs((pulg_db or 0) - pulg_expected) <= 0.1):
                    ok_list.append((codigo, subcat))

        # Reportar
        if out_csv:
            self.stdout.write("sku,subcategoria,modelo,pulg_esperadas,precio_esperado,status,precio_db,pulg_db,categoria_db")
            for row in EXPECTED_TWCAT:
                codigo, modelo, pulg, precio, subcat = row
                key = _normalize_sku_for_match(codigo)
                prods = db_by_sku.get(key, [])
                prod = next((p for p in prods if (p.category and p.category.slug == subcat)), prods[0] if prods else None)
                if not prod:
                    self.stdout.write(f"{codigo},{subcat},{modelo},{pulg},{precio},MISSING,,,")
                else:
                    di = float(prod.diametro_entrada) if prod.diametro_entrada else ""
                    self.stdout.write(
                        f"{prod.sku},{prod.category.slug if prod.category else ''},{modelo},{pulg},{precio},OK,{int(float(prod.price or 0))},{di or ''},{prod.category.slug if prod.category else ''}"
                    )
            return

        self.stdout.write("=" * 70)
        self.stdout.write("AUDITORÍA TWCAT - Convertidores catalíticos")
        self.stdout.write("=" * 70)

        if missing:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR(f"PRODUCTOS NO ENCONTRADOS ({len(missing)}):"))
            for codigo, subcat, modelo, pulg, precio in missing:
                self.stdout.write(f"  - {codigo} (debería estar en {subcat}) | modelo={modelo} | {pulg}\" | ${precio}")

        if wrong_cat:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"SUBCATEGORÍA INCORRECTA ({len(wrong_cat)}):"))
            for codigo, actual, esperada in wrong_cat:
                self.stdout.write(f"  - {codigo}: está en '{actual}', debería estar en '{esperada}'")

        if wrong_price:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"PRECIO INCORRECTO ({len(wrong_price)}):"))
            for codigo, subcat, db_price, expected in wrong_price:
                self.stdout.write(f"  - {codigo} ({subcat}): DB=${db_price} | esperado=${expected}")

        if wrong_pulg:
            self.stdout.write("")
            self.stdout.write(self.style.WARNING(f"MEDIDAS (PULGADAS) INCORRECTAS O FALTANTES ({len(wrong_pulg)}):"))
            for codigo, subcat, db_val, expected in wrong_pulg:
                db_str = f"{db_val}\"" if db_val is not None else "sin dato"
                self.stdout.write(f"  - {codigo} ({subcat}): DB={db_str} | esperado={expected}\"")

        if wrong_modelo:
            self.stdout.write("")
            self.stdout.write(self.style.NOTICE(f"MODELO (forma) no verificado en nombre/ficha ({len(wrong_modelo)}):"))
            for codigo, subcat, nombre, modelo_esperado in wrong_modelo[:10]:
                self.stdout.write(f"  - {codigo}: nombre='{nombre[:50]}...' | esperado={modelo_esperado}")
            if len(wrong_modelo) > 10:
                self.stdout.write(f"  ... y {len(wrong_modelo) - 10} más")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"OK: {len(ok_list)} productos correctos en subcategoría y precio"))
        if ok_list:
            for codigo, subcat in ok_list[:15]:
                self.stdout.write(f"  - {codigo} en {subcat}")
            if len(ok_list) > 15:
                self.stdout.write(f"  ... y {len(ok_list) - 15} más")

        # Resumen productos extra en DB (no en la lista esperada)
        expected_keys = {_normalize_sku_for_match(r[0]) for r in EXPECTED_TWCAT}

        def _is_covered_by_expected(prod):
            """True si el producto está cubierto por la lista oficial (SKU o alias o sufijo -EURO4/-EURO5)."""
            norm = _normalize_sku_for_match(prod.sku)
            if norm in expected_keys:
                return True
            alias = SKU_ALIAS_TO_KEY.get(prod.sku.upper().strip())
            if alias and alias in expected_keys:
                return True
            for suffix in ("-EURO4", "-EURO5"):
                if norm.endswith(suffix):
                    base = norm[: -len(suffix)]
                    if base in expected_keys:
                        return True
            return False

        extra = [p for p in all_twcat if not _is_covered_by_expected(p)]
        if extra:
            self.stdout.write("")
            self.stdout.write(self.style.NOTICE(f"Productos TWCAT en DB que NO están en la lista oficial ({len(extra)}):"))
            for p in extra[:20]:
                cat_slug = p.category.slug if p.category else ""
                self.stdout.write(f"  - {p.sku} | {cat_slug} | ${int(float(p.price or 0))}")
            if len(extra) > 20:
                self.stdout.write(f"  ... y {len(extra) - 20} más")

        self.stdout.write("")
        self.stdout.write("=" * 70)
