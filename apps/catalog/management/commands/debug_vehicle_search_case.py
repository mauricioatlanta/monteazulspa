# -*- coding: utf-8 -*-
"""
Debug dirigido: por qué un producto con ProductCompatibility no aparece en
verified o suggested_brand_wide. Traza paso a paso el builder y el estado del producto.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.catalog.models import (
    Product,
    ProductCompatibility,
    VehicleBrand,
    VehicleModel,
    VehicleEngine,
)
from apps.catalog.services.vehicle_search_result_builder import build_vehicle_result_context
from apps.catalog.services.vehicle_technical_profile import (
    build_vehicle_profile,
    filter_products_by_technical_fit,
    sort_products_by_technical_rank,
)


# Casos fallidos conocidos para debug: (brand_name, model_name, year) -> expected_sku, block
FAILURE_CASES = [
    ("Chevrolet", "Sail", 2014, "2x8", "verified"),
    ("Hyundai", "Accent", 2000, "CAT-HY01", "verified"),
    ("Kia", "Rio", 2000, "CAT-HY01", "verified"),
    ("Chevrolet", "Cruze", 2000, "CLF04", "verified"),
    ("Renault", "Clio", 2000, "CLF06", "verified"),
    ("Chevrolet", "Aveo", 2000, "CLF08", "verified"),
    ("BMW", "Serie 1", 2000, "CLF02", "suggested_brand_wide"),
    ("Hyundai", "i10", 2000, "CLF03", "suggested_brand_wide"),
    ("Audi", "A3", 2000, "CLFO36-AUDI", "suggested_brand_wide"),
]


def _product_data(p: Product) -> Dict[str, Any]:
    return {
        "id": p.id,
        "sku": p.sku,
        "name": getattr(p, "name", None),
        "category": p.category.name if getattr(p, "category", None) else None,
        "category_id": getattr(p, "category_id", None),
        "is_active": getattr(p, "is_active", None),
        "is_publishable": getattr(p, "is_publishable", None),
        "deleted_at": getattr(p, "deleted_at", None),
        "stock": getattr(p, "stock", None),
        "combustible": getattr(p, "combustible", None),
        "euro_norm": getattr(p, "euro_norm", None),
        "recommended_cc_min": getattr(p, "recommended_cc_min", None),
        "recommended_cc_max": getattr(p, "recommended_cc_max", None),
        "quality_score": getattr(p, "quality_score", None),
    }


def _compat_data(c: ProductCompatibility) -> Dict[str, Any]:
    return {
        "product_id": c.product_id,
        "brand_id": c.brand_id,
        "model_id": c.model_id,
        "engine_id": c.engine_id,
        "year_from": c.year_from,
        "year_to": c.year_to,
        "confidence": getattr(c, "confidence", None),
        "notes": getattr(c, "notes", None) or "",
        "is_active": c.is_active,
    }


def _sep(out, char="="):
    out.append(char * 60)


def _trace_verified(
    brand_id: int,
    model_id: int,
    year: int,
    engine_id: Optional[int],
    fuel_type: Optional[str],
    displacement_cc: Optional[int],
    expected_product_id: int,
    out: List[str],
    verbose: bool,
) -> str:
    """Traza paso a paso la rama verified; retorna explicación del fallo o '' si aparece."""
    from apps.catalog.models import Product, ProductCompatibility

    _sep(out)
    out.append("TRACE VERIFIED (paso a paso)")
    _sep(out)

    base_compat = ProductCompatibility.objects.filter(
        brand_id=brand_id,
        model_id=model_id,
        model__isnull=False,
        year_from__lte=year,
        year_to__gte=year,
        is_active=True,
    )
    compat_ids = list(base_compat.values_list("id", flat=True))
    compat_product_ids = list(base_compat.values_list("product_id", flat=True).distinct())
    out.append(f"1) Base compatibilities (exact): count={base_compat.count()}, product_ids={compat_product_ids}")

    if expected_product_id not in compat_product_ids:
        return "excluded because product ID never entered the compatibility queryset (no row with this brand/model/year or model is null)"

    compatibilities = base_compat
    if engine_id:
        exact_engine = base_compat.filter(engine_id=engine_id)
        if exact_engine.exists():
            compatibilities = exact_engine
            out.append(f"2) Con engine_id={engine_id}: usando compat exact_engine, product_ids={list(compatibilities.values_list('product_id', flat=True).distinct())}")
        else:
            compatibilities = base_compat.filter(engine_id__isnull=True)
            out.append(f"2) Con engine_id={engine_id}: sin match exacto, usando engine null. product_ids={list(compatibilities.values_list('product_id', flat=True).distinct())}")
    else:
        if fuel_type:
            compatibilities = compatibilities.filter(fuel_type=fuel_type)
            out.append(f"2) Filtro fuel_type={fuel_type}: product_ids={list(compatibilities.values_list('product_id', flat=True).distinct())}")
        if displacement_cc is not None:
            compatibilities = compatibilities.filter(displacement_cc=displacement_cc)
            out.append(f"2) Filtro displacement_cc={displacement_cc}: product_ids={list(compatibilities.values_list('product_id', flat=True).distinct())}")

    verified_ids = list(compatibilities.values_list("product_id", flat=True).distinct())
    out.append(f"3) verified_ids después de engine/fuel/cc: {verified_ids}")

    if expected_product_id not in verified_ids:
        return "excluded because expected product dropped when applying engine_id / fuel_type / displacement_cc filter on compatibilities"

    # Queryset final de productos (builder ya no filtra por is_publishable en verified)
    qs_verified = Product.objects.filter(
        id__in=verified_ids,
        is_active=True,
        deleted_at__isnull=True,
    )
    final_verified_ids = list(qs_verified.values_list("id", flat=True))
    out.append(f"4) Product.objects.filter(id__in=verified_ids, is_active=True, deleted_at__isnull=True)")
    out.append(f"   IDs finales verified: {final_verified_ids}")

    if expected_product_id not in final_verified_ids:
        p = Product.objects.filter(id=expected_product_id).first()
        if not p:
            return "excluded because product row not found"
        reasons = []
        if not getattr(p, "is_active", True):
            reasons.append("is_active=False")
        if getattr(p, "deleted_at", None) is not None:
            reasons.append("deleted_at is not null")
        if reasons:
            return "excluded because product filtered by catalog queryset: " + ", ".join(reasons)
        return "excluded because not in catalog queryset (unknown)"

    return ""


def _trace_brand_wide(
    brand_id: int,
    model_id: int,
    year: int,
    engine_id: Optional[int],
    fuel_type: Optional[str],
    displacement_cc: Optional[int],
    verified_ids: List[int],
    expected_product_id: int,
    out: List[str],
    verbose: bool,
) -> str:
    """Traza suggested_brand_wide; retorna explicación del fallo o ''."""
    from apps.catalog.models import Product, ProductCompatibility

    _sep(out)
    out.append("TRACE SUGGESTED BRAND-WIDE (paso a paso)")
    _sep(out)

    brand_wide_compat = ProductCompatibility.objects.filter(
        brand_id=brand_id,
        model__isnull=True,
        year_from__lte=year,
        year_to__gte=year,
        is_active=True,
    )
    bw_product_ids = list(brand_wide_compat.values_list("product_id", flat=True).distinct())
    out.append(f"1) Compatibilities model=None, brand_id={brand_id}, year in range: product_ids={bw_product_ids}")

    brand_wide_ids_raw = [pid for pid in bw_product_ids if pid not in verified_ids]
    out.append(f"2) Excluyendo verified_ids: brand_wide_ids_raw={brand_wide_ids_raw}")

    if expected_product_id not in brand_wide_ids_raw:
        if expected_product_id in verified_ids:
            return "excluded because product is in verified (exact match), not brand-wide"
        if expected_product_id not in bw_product_ids:
            return "excluded because product ID never entered brand-wide compatibility queryset (no brand-wide row for this brand/year)"
        return "excluded because product was in verified_ids (duplicate removal)"

    try:
        engine = VehicleEngine.objects.get(id=engine_id) if engine_id else None
    except Exception:
        engine = None
    profile = build_vehicle_profile(
        year=year,
        engine=engine,
        fuel_type=fuel_type,
        displacement_cc=displacement_cc,
    )
    out.append(f"3) Profile: fuel_norm={profile.get('fuel_norm')}, euro_norm={profile.get('euro_norm')}, cc={profile.get('displacement_cc')}")

    qs_before_filter = Product.objects.filter(
        id__in=brand_wide_ids_raw,
        is_active=True,
        deleted_at__isnull=True,
    )
    ids_before = list(qs_before_filter.values_list("id", flat=True))
    out.append(f"4) Product queryset (before technical filter): ids={ids_before}")

    if expected_product_id not in ids_before:
        p = Product.objects.filter(id=expected_product_id).first()
        reasons = []
        if p and not getattr(p, "is_active", True):
            reasons.append("is_active=False")
        if p and getattr(p, "deleted_at", None):
            reasons.append("deleted_at set")
        return "excluded because product not in catalog base queryset (before technical filter): " + ", ".join(reasons) if reasons else "excluded because not in catalog queryset"

    qs_after_filter = filter_products_by_technical_fit(qs_before_filter, profile)
    ids_after_filter = list(qs_after_filter.values_list("id", flat=True))
    out.append(f"5) After filter_products_by_technical_fit: ids={ids_after_filter}")

    if expected_product_id not in ids_after_filter:
        p = Product.objects.filter(id=expected_product_id).first()
        if not p:
            return "excluded because product not found"
        reasons = []
        fuel_norm = profile.get("fuel_norm")
        if fuel_norm and getattr(p, "combustible", None) and p.combustible != fuel_norm:
            reasons.append("technical fuel filter (combustible != profile)")
        euro_norm = profile.get("euro_norm")
        if euro_norm and getattr(p, "euro_norm", None) and p.euro_norm != euro_norm:
            reasons.append("euro_norm filter")
        cc = profile.get("displacement_cc")
        if cc and (getattr(p, "recommended_cc_min", None) is not None or getattr(p, "recommended_cc_max", None) is not None):
            tol = 300 if cc < 2000 else 500
            lo, hi = getattr(p, "recommended_cc_min", None), getattr(p, "recommended_cc_max", None)
            if lo is not None and hi is not None and not (lo <= cc + tol and hi >= cc - tol):
                reasons.append("cc range filter")
        return "excluded by technical filter: " + ", ".join(reasons) if reasons else "excluded by technical filter (unknown)"

    products_sorted = sort_products_by_technical_rank(list(qs_after_filter), profile)
    ids_after_sort = [p.id for p in products_sorted]
    out.append(f"6) After sort_products_by_technical_rank: ids={ids_after_sort}")
    return ""


class Command(BaseCommand):
    help = "Debug por qué un producto con ProductCompatibility no aparece en verified o suggested_brand_wide."

    def add_arguments(self, parser):
        parser.add_argument("--sku", type=str, required=True, help="SKU del producto a depurar")
        parser.add_argument("--verbose", action="store_true", help="Más detalle")
        parser.add_argument("--brand-id", type=int, default=None, help="Opcional: filtrar caso por brand_id")
        parser.add_argument("--model-id", type=int, default=None, help="Opcional: filtrar caso por model_id")
        parser.add_argument("--year", type=int, default=None, help="Opcional: filtrar caso por año")
        parser.add_argument("--sail-compare", action="store_true", help="Incluir comparación Sail 2x6 vs 2x8")

    def handle(self, *args, **options):
        sku = (options.get("sku") or "").strip()
        verbose = options.get("verbose", False)
        brand_id = options.get("brand_id")
        model_id = options.get("model_id")
        year = options.get("year")
        sail_compare = options.get("sail_compare", False)

        if not sku:
            self.stdout.write(self.style.ERROR("--sku es obligatorio."))
            return

        product = Product.objects.filter(sku=sku).select_related("category").first()
        if not product:
            self.stdout.write(self.style.ERROR(f"No existe producto con SKU={sku}"))
            return

        compats = list(
            ProductCompatibility.objects.filter(product_id=product.id, is_active=True)
            .select_related("brand", "model", "engine")
            .order_by("brand__name", "model__name")
        )

        out = []
        _sep(out)
        out.append(f"DEBUG VEHICLE SEARCH CASE — SKU={sku} (product_id={product.id})")
        _sep(out)

        out.append("")
        out.append("1) PRODUCTCOMPATIBILITY BASE DETECTADA")
        _sep(out, "-")
        for c in compats:
            out.append(str(_compat_data(c)))
        if not compats:
            out.append("(ninguna compatibilidad activa para este producto)")

        out.append("")
        out.append("2) DATOS DEL PRODUCTO ESPERADO")
        _sep(out, "-")
        for k, v in _product_data(product).items():
            out.append(f"  {k}: {v}")

        if sail_compare or (sku in ("2x6", "2x8") and product):
            self._append_sail_comparison(out)

        cases = self._build_cases(compats, product, brand_id, model_id, year)
        if not cases:
            out.append("")
            out.append("No hay casos de vehículo que probar para este SKU (o no coinciden --brand-id/--model-id/--year).")
            for line in out:
                self.stdout.write(line)
            return

        for case in cases:
            out.append("")
            _sep(out)
            out.append(f"CASE: {case['label']} | expected_sku={case['expected_sku']} | block={case['block']}")
            _sep(out)

            ctx = build_vehicle_result_context(
                brand_id=case["brand_id"],
                model_id=case["model_id"],
                year=case["year"],
                engine_id=case.get("engine_id"),
                fuel_type=case.get("fuel_type"),
                displacement_cc=case.get("displacement_cc"),
            )

            if ctx is None:
                out.append("build_vehicle_result_context returned None (brand/model/year inválidos).")
                continue

            pv = ctx["products_verified"]
            if hasattr(pv, "values_list"):
                verified_ids = list(pv.values_list("id", flat=True))
                verified_skus = list(pv.values_list("sku", flat=True))
            else:
                verified_ids = [p.id for p in pv]
                verified_skus = [p.sku for p in pv]
            bw_skus = [p.sku for p in ctx["products_suggested_brand_wide"]]

            in_verified = product.id in verified_ids
            in_bw = product.sku in bw_skus

            out.append(f"Builder result: verified={verified_skus}, suggested_brand_wide={bw_skus[:15]}...")
            out.append(f"Expected product in verified? {in_verified} | in suggested_brand_wide? {in_bw}")

            if case["block"] == "verified":
                reason = _trace_verified(
                    case["brand_id"],
                    case["model_id"],
                    case["year"],
                    case.get("engine_id"),
                    case.get("fuel_type"),
                    case.get("displacement_cc"),
                    product.id,
                    out,
                    verbose,
                )
            else:
                pv = ctx["products_verified"]
                verified_ids_list = list(pv.values_list("id", flat=True)) if hasattr(pv, "values_list") else [p.id for p in pv]
                reason = _trace_brand_wide(
                    case["brand_id"],
                    case["model_id"],
                    case["year"],
                    case.get("engine_id"),
                    case.get("fuel_type"),
                    case.get("displacement_cc"),
                    verified_ids_list,
                    product.id,
                    out,
                    verbose,
                )

            out.append("")
            out.append("4) EXPLICACIÓN FINAL DEL FALLO")
            _sep(out, "-")
            out.append(reason if reason else "OK — el producto SÍ aparece en el bloque esperado.")

        for line in out:
            self.stdout.write(line)

    def _build_cases(
        self,
        compats: List[ProductCompatibility],
        product: Product,
        brand_id: Optional[int],
        model_id: Optional[int],
        year: Optional[int],
    ) -> List[Dict[str, Any]]:
        cases = []
        for c in compats:
            if brand_id is not None and c.brand_id != brand_id:
                continue
            if model_id is not None and c.model_id != model_id:
                continue
            y = (c.year_from + c.year_to) // 2 if c.year_from <= c.year_to else c.year_from
            if year is not None and (y < c.year_from or y > c.year_to):
                continue
            if year is not None and year != y:
                continue

            if c.model_id:
                engine_id = c.engine_id
                if not engine_id:
                    first = VehicleEngine.objects.filter(model_id=c.model_id).first()
                    engine_id = first.id if first else None
                model = VehicleModel.objects.get(id=c.model_id)
                brand = VehicleBrand.objects.get(id=c.brand_id)
                label = f"{brand.name} {model.name} {y}"
                cases.append({
                    "label": label,
                    "brand_id": c.brand_id,
                    "model_id": c.model_id,
                    "year": y,
                    "engine_id": engine_id,
                    "fuel_type": getattr(c.engine, "fuel_type", None) if c.engine else c.fuel_type,
                    "displacement_cc": getattr(c.engine, "displacement_cc", None) if c.engine else c.displacement_cc,
                    "expected_sku": product.sku,
                    "block": "verified",
                })
            else:
                model = VehicleModel.objects.filter(brand_id=c.brand_id).first()
                if not model:
                    continue
                brand = VehicleBrand.objects.get(id=c.brand_id)
                label = f"{brand.name} {model.name} {y} (brand-wide)"
                cases.append({
                    "label": label,
                    "brand_id": c.brand_id,
                    "model_id": model.id,
                    "year": y,
                    "engine_id": None,
                    "fuel_type": c.fuel_type,
                    "displacement_cc": c.displacement_cc,
                    "expected_sku": product.sku,
                    "block": "suggested_brand_wide",
                })
        return cases

    def _append_sail_comparison(self, out: List[str]) -> None:
        from apps.catalog.models import Product, ProductCompatibility

        _sep(out)
        out.append("5) VALIDACIÓN ESPECÍFICA SAIL 2x6 vs 2x8")
        _sep(out)

        p_2x6 = Product.objects.filter(sku="2x6").first()
        p_2x8 = Product.objects.filter(sku="2x8").first()
        if not p_2x6 or not p_2x8:
            out.append("Faltan producto 2x6 o 2x8 en catálogo.")
            return

        # Chevrolet Sail: brand/model
        sail_brand = VehicleBrand.objects.filter(name__icontains="Chevrolet").first()
        sail_model = VehicleModel.objects.filter(name__icontains="Sail", brand=sail_brand).first() if sail_brand else None
        if not sail_brand or not sail_model:
            out.append("No se encontró Chevrolet Sail en BD.")
            return

        compats_2x6 = list(ProductCompatibility.objects.filter(product=p_2x6, brand=sail_brand, model=sail_model, is_active=True))
        compats_2x8 = list(ProductCompatibility.objects.filter(product=p_2x8, brand=sail_brand, model=sail_model, is_active=True))
        out.append(f"Compatibilidades 2x6 (Sail): {len(compats_2x6)} — {[_compat_data(c) for c in compats_2x6]}")
        out.append(f"Compatibilidades 2x8 (Sail): {len(compats_2x8)} — {[_compat_data(c) for c in compats_2x8]}")

        year = 2014
        ctx = build_vehicle_result_context(
            brand_id=sail_brand.id,
            model_id=sail_model.id,
            year=year,
            engine_id=None,
            fuel_type=None,
            displacement_cc=None,
        )
        if ctx:
            verified = list(ctx["products_verified"])
            out.append(f"Builder Sail 2014 verified SKUs: {[p.sku for p in verified]}")
            out.append(f"2x6 en verified: {any(p.sku == '2x6' for p in verified)}")
            out.append(f"2x8 en verified: {any(p.sku == '2x8' for p in verified)}")
            out.append(f"Producto 2x6: is_publishable={getattr(p_2x6, 'is_publishable', None)}, is_active={getattr(p_2x6, 'is_active', None)}, deleted_at={getattr(p_2x6, 'deleted_at', None)}")
            out.append(f"Producto 2x8: is_publishable={getattr(p_2x8, 'is_publishable', None)}, is_active={getattr(p_2x8, 'is_active', None)}, deleted_at={getattr(p_2x8, 'deleted_at', None)}")
        _sep(out)
