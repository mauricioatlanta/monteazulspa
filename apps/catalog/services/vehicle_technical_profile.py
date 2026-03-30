# -*- coding: utf-8 -*-
"""
Perfil técnico del vehículo e inferencia de norma Euro para filtrar sugeridos
(brand_wide y other) por combustible, norma Euro y cilindrada.

Incluye ranking técnico para ordenar sugeridos por relevancia:
1. Misma norma + mismo combustible + rango cc más cercano
2. Misma norma + combustible correcto
3. Resto (marca wide u otras sugerencias)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.db.models import Q, QuerySet

from apps.catalog.models import Product, VehicleEngine
from apps.catalog.services.technical_rules import _norm_fuel, year_to_euro


def infer_euro_norm(year: Optional[int]) -> Optional[str]:
    """
    Infiere norma Euro a partir del año del vehículo (fallback).
    Coincide con las opciones de Product.euro_norm (EURO2–EURO5).

    A futuro conviene priorizar: norma en motor/fitment/tabla año-modelo-mercado,
    y usar esta inferencia solo cuando no exista fuente más confiable.
    """
    if year is None:
        return None
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    if y >= 2018:
        return "EURO5"  # Product no tiene EURO6; usar EURO5 como máximo
    if y >= 2012:
        return "EURO5"
    if y >= 2006:
        return "EURO4"
    if y >= 2000:
        return "EURO3"
    return "EURO2"


def build_vehicle_profile(
    year: int,
    engine: Optional[VehicleEngine] = None,
    fuel_type: Optional[str] = None,
    displacement_cc: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Construye un perfil técnico para filtrar productos sugeridos.

    - fuel_type y displacement_cc pueden venir del motor o del request (búsqueda sin motor).
    """
    fuel = None
    cc = None
    if engine:
        fuel = engine.fuel_type
        cc = engine.displacement_cc
    if fuel_type:
        fuel = fuel or fuel_type
    if displacement_cc is not None:
        cc = cc or displacement_cc

    fuel_norm = _norm_fuel(fuel) if fuel else ""
    euro_norm = infer_euro_norm(year) or year_to_euro(year)

    return {
        "year": year,
        "fuel_type": fuel,
        "fuel_norm": fuel_norm,  # BENCINA / DIESEL para Product.combustible
        "displacement_cc": cc,
        "euro_norm": euro_norm,
    }


def filter_products_by_technical_fit(
    qs: QuerySet[Product],
    profile: Dict[str, Any],
) -> QuerySet[Product]:
    """
    Filtra un queryset de productos (sugeridos) por perfil técnico del vehículo.

    Reglas:
    - Combustible: producto debe coincidir o tener combustible null (universal).
    - Norma Euro: producto debe coincidir o tener euro_norm null. Nunca mostrar Euro menor al del vehículo de forma agresiva (ya cubierto por filtro igual o null).
    - Cilindrada: producto.recommended_cc_min/max debe contener vehicle_cc con tolerancia (300 cc si < 2000, else 500 cc), o ambos null.

    Si el perfil no tiene datos, no restringe (fallback seguro).
    """
    if not profile:
        return qs

    # 1) Combustible
    fuel_norm = profile.get("fuel_norm")
    if fuel_norm:
        qs = qs.filter(Q(combustible=fuel_norm) | Q(combustible__isnull=True))

    # 2) Norma Euro
    euro_norm = profile.get("euro_norm")
    if euro_norm:
        qs = qs.filter(Q(euro_norm=euro_norm) | Q(euro_norm__isnull=True))

    # 3) Cilindrada con tolerancia
    cc = profile.get("displacement_cc")
    if cc is not None and cc > 0:
        tolerance = 300 if cc < 2000 else 500
        cc_lo = cc - tolerance
        cc_hi = cc + tolerance
        # Producto aplica si su rango [min,max] intersecta [cc_lo, cc_hi], o no tiene rango
        qs = qs.filter(
            Q(recommended_cc_min__isnull=True, recommended_cc_max__isnull=True)
            | (
                Q(recommended_cc_min__lte=cc_hi)
                & Q(recommended_cc_max__gte=cc_lo)
            )
        )

    return qs


def _product_technical_rank_key(product: Product, profile: Dict[str, Any]) -> Tuple[int, int, int, int]:
    """
    Clave de orden para ranking técnico de sugeridos (mayor = mejor).

    Orden deseado:
    1. Misma norma + mismo combustible + rango cc que contiene al vehículo (y más cercano = mejor)
    2. Misma norma + combustible correcto
    3. Resto

    Retorna (euro_match, fuel_match, cc_score, cc_tiebreaker_neg_width).
    - euro_match: 1 si producto.euro_norm == perfil, 0 si no.
    - fuel_match: 1 si producto.combustible == perfil, 0 si no.
    - cc_score: 2 si cc vehículo dentro de [min,max], 1 si rango existe y solapa, 0 si no hay rango.
    - cc_tiebreaker_neg_width: cuando cc dentro de rango, -(max-min) para que rango más estrecho salga primero; si no, 0.
    """
    euro_norm = profile.get("euro_norm")
    fuel_norm = profile.get("fuel_norm")
    cc = profile.get("displacement_cc")

    euro_match = 1 if (euro_norm and getattr(product, "euro_norm", None) == euro_norm) else 0
    fuel_match = 1 if (fuel_norm and getattr(product, "combustible", None) == fuel_norm) else 0

    cc_score = 0
    cc_tiebreaker = 0
    if cc and getattr(product, "recommended_cc_min", None) is not None and getattr(product, "recommended_cc_max", None) is not None:
        lo, hi = product.recommended_cc_min, product.recommended_cc_max
        if lo <= cc <= hi:
            cc_score = 2
            cc_tiebreaker = -((hi - lo) or 0)  # rango más estrecho primero
        else:
            cc_score = 1  # rango existe y ya pasó filtro (solapa)
    return (euro_match, fuel_match, cc_score, cc_tiebreaker)


def sort_products_by_technical_rank(
    products: List[Product],
    profile: Dict[str, Any],
) -> List[Product]:
    """
    Ordena una lista de productos sugeridos por relevancia técnica.

    Mejores primero: misma norma Euro, mismo combustible, rango cc que contiene
    al vehículo (y entre esos, rango más estrecho primero).
    """
    if not profile or not products:
        return products
    return sorted(
        products,
        key=lambda p: _product_technical_rank_key(p, profile),
        reverse=True,
    )


# Alias público para tests de integridad (validación de orden de ranking).
product_technical_rank_key = _product_technical_rank_key
