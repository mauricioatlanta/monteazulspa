# -*- coding: utf-8 -*-
"""
Completa diametro_entrada y diametro_salida para productos de escape que se pueden
deducir automáticamente según las reglas técnicas del catálogo Monte Azul.

Reglas aplicadas:
- Flexibles: SKU tipo DIAMETROxLARGO (ej. 2X6 → diam 2", largo 6" → largo_mm = 152).
- Catalíticos/TWCAT: código en SKU 200→2", 225→2.25", 250→2.5", 300→3".
- CLF/CAT sin código en SKU: se infiere diámetro desde compatibilidades (cilindrada + combustible),
  desde texto del producto, o desde mapa conocido CLF→cc cuando no hay compatibilidades cargadas.

Uso:
  python manage.py fill_catalog_diameters [--dry-run]
"""
import re
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductCompatibility
from apps.catalog.services.technical_rules import allowed_diameters


def _s(v):
    return "" if v is None else str(v)


def _norm(v):
    return (
        _s(v).strip().upper()
        .replace("Á", "A").replace("É", "E").replace("Í", "I").replace("Ó", "O").replace("Ú", "U")
    )


def _infer_cc_from_text(text, product):
    """Extrae cilindrada (cc) de texto o de compatibilidades."""
    vals = []
    text = _norm(text).replace(",", ".")
    # Patrones 1.6 → 1600, 2.0 → 2000
    for a, b in re.findall(r"(?<!\d)(\d)\.(\d)(?!\d)", text):
        vals.append(int(a + b + "00"))
    for n in re.findall(
        r"(?<!\d)(1000|1200|1300|1400|1500|1600|1700|1800|1900|2000|2200|2300|2400|2500|2700|2800|3000|3200|3500|3600|4000|4500|5000)(?!\d)",
        text,
    ):
        vals.append(int(n))
    vals = sorted(set(vals))
    return vals[0] if vals else None


# Mapa conocido SKU CLF/CAT → cilindrada (cc). Se usa cuando no hay ProductCompatibility.
# Puedes ampliarlo según tu catálogo (ej. CLF01=1600, CAT-HY01=1600).
CLF_CAT_CC_MAP = {
    "CAT-HY01": 1600,
    "CLF001": 1600,
    "CLF002": 2000,
    "CLF003": 2000,
    "CLF004": 2000,
    "CLF005": 2400,
    "CLF006": 2000,
    "CLF007": 2000,
    "CLF008": 2000,
    "CLF01": 1600,
    "CLF02": 2000,
    "CLF04": 1400,
    "CLF08": 1800,
    "CLFO36-AUDI": 2000,
    "RENAULT-CLIO": 1600,
}


def _get_cc_from_clf_map(sku):
    """Devuelve cilindrada para SKUs CLF/CAT conocidos (normalizado a mayúsculas, sin espacios)."""
    if not sku:
        return None
    key = _s(sku).strip().upper()
    if key in CLF_CAT_CC_MAP:
        return CLF_CAT_CC_MAP[key]
    return None


def _get_cc_from_compatibilities(product):
    """Obtiene cilindrada del primer registro de compatibilidad (displacement_cc o engine)."""
    comp = (
        product.compatibilities.filter(is_active=True)
        .select_related("engine")
        .order_by("id")
        .first()
    )
    if not comp:
        return None
    if comp.displacement_cc:
        return comp.displacement_cc
    if comp.engine_id and comp.engine.displacement_cc:
        return comp.engine.displacement_cc
    return None


def _infer_fuel(product, text):
    """Combustible desde producto o inferido del texto."""
    if product.combustible in ("BENCINA", "DIESEL"):
        return product.combustible
    t = _norm(text)
    if any(x in t for x in ["DIESEL", "TDI", "HDI", "CRDI", "CDTI", "DTI", "TURBO DIESEL"]):
        return "DIESEL"
    if any(x in t for x in ["BENCINA", "GASOLINA", "NAFTA"]):
        return "BENCINA"
    return ""


def _infer_allowed_diams(cc, fuel):
    """
    Wrapper histórico para mantener compatibilidad con llamadas existentes dentro
    de este comando. Delegamos en la función reusable allowed_diameters.
    """
    return allowed_diameters(cc, fuel)


# Flexibles: SKU tipo 1.75X4, 2X6, 2.5X8 (diámetro X largo en pulgadas)
FLEX_PATTERN = re.compile(r"^\s*(\d(?:\.\d+)?)\s*[Xx]\s*(\d+(?:\.\d+)?)\s*$", re.IGNORECASE)

# Diámetro en SKU: 200→2", 225→2.25", 250→2.5", 300→3"
DIAM_CODE_PATTERN = re.compile(r"(200|225|250|300)(?!\d)")
DIAM_CODE_MAP = {"200": 2.0, "225": 2.25, "250": 2.5, "300": 3.0}


def _fill_flexible_from_sku(product):
    """Si el SKU es tipo DIAMxLARGO, completa diametro_entrada, diametro_salida, largo_mm."""
    m = FLEX_PATTERN.match(_s(product.sku))
    if not m:
        return False
    try:
        diam = float(m.group(1))
        largo_pulg = float(m.group(2))
    except (ValueError, TypeError):
        return False
    largo_mm = round(largo_pulg * 25.4)
    changed = False
    update_fields = []

    if product.diametro_entrada is None:
        product.diametro_entrada = Decimal(str(round(diam, 2)))
        changed = True
        update_fields.append("diametro_entrada")
    if product.diametro_salida is None:
        product.diametro_salida = Decimal(str(round(diam, 2)))
        changed = True
        update_fields.append("diametro_salida")
    if getattr(product, "largo_mm", None) in (None, 0):
        product.largo_mm = largo_mm
        changed = True
        update_fields.append("largo_mm")

    if changed and update_fields:
        product.save(update_fields=update_fields)
    return changed


def _fill_diam_from_sku_code(product):
    """Si el SKU contiene 200/225/250/300, asigna ese diámetro."""
    sku = _s(product.sku).upper()
    m = DIAM_CODE_PATTERN.search(sku)
    if not m:
        return False
    diam = DIAM_CODE_MAP.get(m.group(1))
    if diam is None:
        return False
    changed = False
    update_fields = []
    if product.diametro_entrada is None:
        product.diametro_entrada = Decimal(str(diam))
        changed = True
        update_fields.append("diametro_entrada")
    if product.diametro_salida is None:
        product.diametro_salida = Decimal(str(diam))
        changed = True
        update_fields.append("diametro_salida")
    if changed and update_fields:
        product.save(update_fields=update_fields)
    return changed


def _fill_clf_cat_from_cc_fuel(product, text):
    """
    Para CLF/CAT sin diámetro: obtiene cc (compatibilidades, texto o mapa SKU) y combustible,
    aplica reglas Monte Azul y asigna el primer diámetro permitido.
    """
    cc = _get_cc_from_compatibilities(product)
    if cc is None:
        cc = _infer_cc_from_text(text, product)
    if cc is None:
        cc = _get_cc_from_clf_map(product.sku)
    if not cc:
        return False

    fuel = _infer_fuel(product, text)
    allowed = _infer_allowed_diams(cc, fuel)
    if not allowed:
        return False

    diam = allowed[0]
    changed = False
    update_fields = []
    if product.diametro_entrada is None:
        product.diametro_entrada = Decimal(str(diam))
        changed = True
        update_fields.append("diametro_entrada")
    if product.diametro_salida is None:
        product.diametro_salida = Decimal(str(diam))
        changed = True
        update_fields.append("diametro_salida")
    if changed and update_fields:
        product.save(update_fields=update_fields)
    return changed


def _is_flexible_sku(sku):
    return bool(FLEX_PATTERN.match(_s(sku)))


def _is_catalitico_like(sku, category_name):
    """CLF, TWCAT, CAT- en SKU o categoría de catalíticos."""
    sku = _s(sku).upper()
    cat = _norm(_s(category_name))
    if "CLF" in sku or sku.startswith("TWCAT") or sku.startswith("CAT-"):
        return True
    if "CATALITICO" in cat or "CATALITICO" in sku:
        return True
    return False


class Command(BaseCommand):
    help = (
        "Completa diametro_entrada/diametro_salida (y largo_mm en flexibles) usando reglas "
        "del catálogo: flexibles X, códigos 200/225/250/300, y CLF/CAT por cilindrada+combustible."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se actualizaría, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        qs = (
            Product.objects.filter(deleted_at__isnull=True)
            .filter(diametro_entrada__isnull=True)
            .select_related("category", "category__parent")
            .prefetch_related("compatibilities__engine")
            .order_by("category__name", "sku")
        )

        stats = {"flexibles": 0, "diam_sku": 0, "clf_cat_cc": 0, "unchanged": 0}

        for product in qs:
            cat = product.category.name if product.category_id else ""
            parent = product.category.parent.name if getattr(product.category, "parent_id", None) else ""
            text = " ".join([
                _s(product.sku),
                _s(product.name),
                cat,
                parent,
                _s(getattr(product, "description", "")),
                _s(getattr(product, "euro_norm", "")),
                _s(product.combustible),
            ])

            updated = False

            if _is_flexible_sku(product.sku):
                if not dry_run and _fill_flexible_from_sku(product):
                    stats["flexibles"] += 1
                    updated = True
                elif dry_run:
                    m = FLEX_PATTERN.match(_s(product.sku))
                    if m and product.diametro_entrada is None:
                        stats["flexibles"] += 1
                        self.stdout.write(
                            f"  [FLEX] {product.sku} → diam {m.group(1)}\", largo {m.group(2)}\""
                        )
                        updated = True

            if not updated:
                mm = DIAM_CODE_PATTERN.search(_s(product.sku).upper())
                if mm and product.diametro_entrada is None:
                    diam_val = DIAM_CODE_MAP.get(mm.group(1))
                    if dry_run:
                        stats["diam_sku"] += 1
                        self.stdout.write(f"  [CODE] {product.sku} → {diam_val}\"")
                    else:
                        if _fill_diam_from_sku_code(product):
                            stats["diam_sku"] += 1
                    updated = True

            if not updated and _is_catalitico_like(product.sku, cat):
                if not dry_run and _fill_clf_cat_from_cc_fuel(product, text):
                    stats["clf_cat_cc"] += 1
                    updated = True
                elif dry_run:
                    cc = (
                        _get_cc_from_compatibilities(product)
                        or _infer_cc_from_text(text, product)
                        or _get_cc_from_clf_map(product.sku)
                    )
                    fuel = _infer_fuel(product, text)
                    allowed = _infer_allowed_diams(cc, fuel) if cc else []
                    if allowed:
                        stats["clf_cat_cc"] += 1
                        self.stdout.write(
                            f"  [CLF/CAT] {product.sku} cc={cc} fuel={fuel} → diam {allowed[0]}\""
                        )
                        updated = True

            if not updated:
                stats["unchanged"] += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Flexibles: {stats['flexibles']}, Por código SKU: {stats['diam_sku']}, "
                f"CLF/CAT por cc: {stats['clf_cat_cc']}, Sin cambio: {stats['unchanged']}"
            )
        )
        if dry_run and (stats["flexibles"] or stats["diam_sku"] or stats["clf_cat_cc"]):
            self.stdout.write(
                self.style.WARNING("Ejecuta sin --dry-run para aplicar los cambios.")
            )
