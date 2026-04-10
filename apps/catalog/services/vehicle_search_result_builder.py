# -*- coding: utf-8 -*-
"""
Constructor central de resultados de búsqueda por vehículo.

Una sola función, build_vehicle_result_context(), usada por:
- core.views (página de resultados por vehículo)
- catalog.views_vehicle_search (API vehicle_products_api)
- management command test_vehicle_search_integrity

Garantiza que verified, suggested_brand_wide y suggested_other se construyan
siempre con la misma lógica (compatibilidad exacta, perfil técnico, filtro y ranking).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Q, QuerySet

from apps.catalog.models import (
    Product,
    ProductCompatibility,
    VehicleBrand,
    VehicleEngine,
    VehicleModel,
)
from apps.catalog.public_visibility import exclude_removed_products, removed_product_q
from apps.catalog.services.vehicle_technical_profile import (
    build_vehicle_profile,
    filter_products_by_technical_fit,
    sort_products_by_technical_rank,
)
from apps.catalog.services.technical_rules import _norm_fuel


def get_diameter_range(cc: Optional[int]) -> tuple[Decimal, Decimal]:
    if not cc:
        return (Decimal("1.75"), Decimal("2.25"))

    try:
        cc_int = int(cc)
    except (TypeError, ValueError):
        return (Decimal("1.75"), Decimal("2.25"))

    if cc_int <= 1400:
        return (Decimal("1.50"), Decimal("1.75"))
    if cc_int <= 1600:
        return (Decimal("1.75"), Decimal("2.25"))
    if cc_int <= 2000:
        return (Decimal("2.00"), Decimal("2.25"))
    if cc_int <= 2500:
        return (Decimal("2.25"), Decimal("2.50"))
    return (Decimal("2.50"), Decimal("3.00"))


def get_universal_catalysts(
    *,
    year: int,
    engine: Optional[VehicleEngine] = None,
    fuel_type: Optional[str] = None,
    displacement_cc: Optional[int] = None,
    exclude_product_ids: Optional[List[int]] = None,
) -> QuerySet[Product]:
    cc = None
    fuel_raw = None
    if engine:
        cc = engine.displacement_cc
        fuel_raw = engine.fuel_type
    if displacement_cc is not None:
        cc = cc or displacement_cc
    if fuel_type:
        fuel_raw = fuel_raw or fuel_type

    fuel_norm = _norm_fuel(fuel_raw) if fuel_raw else ""
    min_d, max_d = get_diameter_range(cc)

    qs = (
        exclude_removed_products(
            Product.objects.filter(
                deleted_at__isnull=True,
                is_active=True,
            )
        )
        .filter(
            Q(category__slug__startswith="cataliticos")
            | Q(category__slug__in=["convertidores-cataliticos", "cataliticos-universales", "cataliticos"])
        )
        .select_related("category")
        .prefetch_related("images")
    )

    if exclude_product_ids:
        qs = qs.exclude(id__in=[int(x) for x in exclude_product_ids if x])

    qs = qs.filter(
        diametro_entrada__gte=min_d,
        diametro_entrada__lte=max_d,
    )

    if fuel_norm in ("DIESEL", "BENCINA"):
        qs = qs.filter(combustible=fuel_norm)

    allowed_euro_values: Optional[tuple[str, ...]] = None
    try:
        y = int(year)
        if y >= 2015:
            allowed_euro_values = ("EURO5",)
        elif y >= 2010:
            allowed_euro_values = ("EURO4", "EURO5")
        elif y >= 2005:
            allowed_euro_values = ("EURO3", "EURO4")
    except (TypeError, ValueError):
        allowed_euro_values = None

    if allowed_euro_values:
        qs = qs.filter(Q(euro_norm__in=allowed_euro_values) | Q(euro_norm__isnull=True))

    return qs.distinct().order_by("diametro_entrada", "sku", "name")


def build_vehicle_result_context(
    brand_id: int,
    model_id: int,
    year: int,
    engine_id: Optional[int] = None,
    fuel_type: Optional[str] = None,
    displacement_cc: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """
    Construye el contexto de resultados por vehículo separando direct fit vs universales.

    Parámetros:
        brand_id, model_id, year: obligatorios.
        engine_id: opcional; si se pasa, se prioriza compatibilidad por motor.
        fuel_type, displacement_cc: opcionales; para búsqueda sin motor (híbrido).

    Reglas de negocio:
        CARRIL 1 - Direct Fit:
        - Productos con compatibilidad específica al modelo del vehículo (model no nulo).
        - Filtro principal: brand + model + year.
        - Si hay engine_id, priorizar compatibilidad por motor; si no existe, aceptar engine null.
        - No dependen de cilindrada/combustible como criterio principal.

        CARRIL 2 - Universales:
        - Productos que se ajustan por perfil técnico: año + combustible + cilindrada.
        - Pueden tener compatibilidad amplia por marca (model=None) o ser sugeridos técnicamente.
        - Marca y modelo NO son criterio dominante; el perfil técnico sí lo es.
        - Filtrados y rankeados por coincidencia técnica (euro_norm, fuel, cc).

    Retorna None si brand/model/year no son válidos o no existen en BD.
    Retorna dict con: profile, products_direct_fit, products_universal_verified,
    products_suggested_other, fitment, brand, model, engine, counts.
    """
    if not all([brand_id, model_id, year]):
        return None
    try:
        year = int(year)
    except (ValueError, TypeError):
        return None

    try:
        brand = VehicleBrand.objects.get(id=brand_id)
        model = VehicleModel.objects.get(id=model_id)
        engine = VehicleEngine.objects.get(id=engine_id) if engine_id else None
    except (VehicleBrand.DoesNotExist, VehicleModel.DoesNotExist, VehicleEngine.DoesNotExist):
        return None

    # Construir perfil técnico del vehículo (para universales)
    profile = build_vehicle_profile(
        year=year,
        engine=engine,
        fuel_type=fuel_type,
        displacement_cc=displacement_cc,
    )

    # ========== CARRIL 1: DIRECT FIT (por modelo específico) ==========
    # Compatibilidad específica al modelo (model no nulo).
    # Criterio principal: brand + model + year.
    # Si hay engine_id, priorizar por motor; si no existe, aceptar engine null.
    direct_fit_compatibilities = ProductCompatibility.objects.filter(
        brand_id=brand_id,
        model_id=model_id,
        model__isnull=False,
        year_from__lte=year,
        year_to__gte=year,
        is_active=True,
    ).exclude(removed_product_q("product__"))

    if engine_id:
        exact_engine = direct_fit_compatibilities.filter(engine_id=engine_id)
        if exact_engine.exists():
            direct_fit_compatibilities = exact_engine
        else:
            direct_fit_compatibilities = direct_fit_compatibilities.filter(engine_id__isnull=True)

    direct_fit_ids = list(direct_fit_compatibilities.values_list("product_id", flat=True).distinct())

    # Direct fit: no exigir is_publishable para no excluir por calidad/score.
    products_direct_fit = exclude_removed_products(
        Product.objects.filter(
            id__in=direct_fit_ids,
            is_active=True,
            deleted_at__isnull=True,
        )
    ).select_related("category").prefetch_related("images", "compatibilities")

    # ========== CARRIL 2: UNIVERSALES (por perfil técnico) ==========
    # Criterio principal: año + combustible + cilindrada.
    # Marca y modelo NO son criterio dominante.

    # 2A) Compatibilidad amplia por marca (model=None): universales con registro de compatibilidad.
    brand_wide_compat = ProductCompatibility.objects.filter(
        brand_id=brand_id,
        model__isnull=True,
        year_from__lte=year,
        year_to__gte=year,
        is_active=True,
    ).exclude(removed_product_q("product__"))

    # Filtrar por perfil técnico (fuel_type y displacement_cc si están disponibles)
    if fuel_type:
        brand_wide_compat = brand_wide_compat.filter(
            Q(fuel_type=fuel_type) | Q(fuel_type__isnull=True)
        )
    if displacement_cc is not None:
        brand_wide_compat = brand_wide_compat.filter(
            Q(displacement_cc=displacement_cc) | Q(displacement_cc__isnull=True)
        )

    brand_wide_ids_raw = list(brand_wide_compat.values_list("product_id", flat=True).distinct())
    brand_wide_ids_filtered = [pid for pid in brand_wide_ids_raw if pid not in direct_fit_ids]

    # Productos universales con compatibilidad amplia por marca
    qs_brand_wide = exclude_removed_products(
        Product.objects.filter(
            id__in=brand_wide_ids_filtered,
            is_active=True,
            deleted_at__isnull=True,
        )
    ).select_related("category").prefetch_related("images")
    qs_brand_wide = filter_products_by_technical_fit(qs_brand_wide, profile)
    products_brand_wide: List[Product] = list(qs_brand_wide)
    products_brand_wide = sort_products_by_technical_rank(products_brand_wide, profile)
    brand_wide_ids = [p.id for p in products_brand_wide]

    # 2B) Sugerencias técnicas universales (sin depender de compatibilidad registrada)
    exclude_for_other = direct_fit_ids + brand_wide_ids

    products_suggested_qs: QuerySet[Product] = get_universal_catalysts(
        year=year,
        engine=engine,
        exclude_product_ids=exclude_for_other,
        fuel_type=fuel_type,
        displacement_cc=displacement_cc,
    )
    products_suggested_qs = filter_products_by_technical_fit(products_suggested_qs, profile)
    if products_direct_fit.exists():
        products_suggested_qs = products_suggested_qs.exclude(diametro_entrada__gt=Decimal("2.50"))
    products_suggested_technical: List[Product] = list(products_suggested_qs[:24])

    # Combinar universales: brand_wide + sugerencias técnicas
    products_universal_all = products_brand_wide + products_suggested_technical

    # Si el usuario indicó combustible diésel, forzar que los universales sean diésel
    if fuel_type == "DIESEL":
        diesel_categories = {"cataliticos-twc-diesel"}

        def _is_diesel_product(p: Product) -> bool:
            slug = getattr(getattr(p, "category", None), "slug", "") or ""
            if slug in diesel_categories:
                return True
            combustible = getattr(p, "combustible", None)
            return combustible == "DIESEL"

        products_universal_all = [p for p in products_universal_all if _is_diesel_product(p)]

        # Fallback a catálogo diésel global si no quedó nada
        if not products_universal_all:
            diesel_qs: QuerySet[Product] = Product.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
            ).select_related("category")
            diesel_qs = [p for p in exclude_removed_products(diesel_qs) if _is_diesel_product(p)]
            diesel_qs = sort_products_by_technical_rank(list(diesel_qs), profile)[:20]
            products_universal_all = diesel_qs

    # Reordenar todos los universales por ranking técnico
    products_universal_verified = sort_products_by_technical_rank(products_universal_all, profile)

    fitment = {
        "brand": brand.name,
        "model": model.name,
        "year": year,
        "engine": engine.name if engine else None,
        "fuel_type": profile.get("fuel_type") or (getattr(engine, "fuel_type", None) if engine else fuel_type),
        "displacement_cc": profile.get("displacement_cc") or (getattr(engine, "displacement_cc", None) if engine else displacement_cc),
    }

    return {
        "profile": profile,
        # Nuevos campos separados por tipo
        "products_direct_fit": products_direct_fit,
        "products_universal_verified": products_universal_verified,
        # Campos legacy para compatibilidad con views/templates actuales
        "products": products_direct_fit,  # Mantener para no romper template actual
        "products_verified": products_direct_fit,
        "products_suggested": products_universal_verified,
        # Campos legacy para API (views_vehicle_search.py)
        "products_suggested_brand_wide": products_brand_wide,
        "products_suggested_other": products_suggested_technical,
        "count": products_direct_fit.count(),
        "count_direct_fit": products_direct_fit.count(),
        "count_universal": len(products_universal_verified),
        "count_suggested": len(products_suggested_technical),
        "fitment": fitment,
        "brand": brand,
        "model": model,
        "engine": engine,
    }
