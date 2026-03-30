# -*- coding: utf-8 -*-
"""
Helpers para backfill de ProductCompatibility: normalización de texto,
detección de marca/modelo y criterios de producto vehicular.

Criterios de negocio:
- Marca + modelo detectados -> compatibilidad específica (un registro).
- Solo marca detectada -> compatibilidad general por marca (un registro por cada modelo de esa marca).
- Varias aplicaciones explícitas en el nombre (ej. "Hyundai Accent / Kia Rio") -> varias compatibilidades.
"""
import re
import unicodedata
from typing import Optional, Tuple, List

from django.db.models import QuerySet


# Categorías cuyo slug indica producto con aplicación vehicular (Direct Fit / CLF / Ensamble Directo)
VEHICLE_CATEGORY_SLUG_PARTS = ("clf", "ensamble-directo", "direct-fit")

# Categorías universales: no crear compatibilidad
UNIVERSAL_CATEGORY_SLUG_PARTS = ("flexibles", "colas", "silenciador", "resonador")


def normalize_vehicle_text(text: str) -> str:
    """Minúsculas, quitar tildes, guiones/underscores a espacios, colapsar espacios."""
    if not text:
        return ""
    s = (text or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[-_]+", " ", s)
    return " ".join(s.split())


def _word_boundary_pattern(word: str) -> re.Pattern:
    """Patrón para que word aparezca como palabra completa."""
    escaped = re.escape(word)
    return re.compile(r"(?<!\w)" + escaped + r"(?!\w)", re.IGNORECASE)


def detect_brand(text: str, brands_qs: QuerySet) -> Tuple[Optional[object], str]:
    """
    Busca una sola marca que aparezca como palabra completa en text.
    Retorna (brand, rest_text) o (None, text) si hay 0 o varias coincidencias.
    """
    if not text or not brands_qs.exists():
        return None, text or ""
    normalized = normalize_vehicle_text(text)
    if not normalized:
        return None, text
    tokens = set(normalized.split())
    matched = []
    for brand in brands_qs:
        name_norm = normalize_vehicle_text(brand.name)
        if not name_norm:
            continue
        brand_words = name_norm.split()
        if all(w in tokens for w in brand_words):
            matched.append(brand)
    if len(matched) == 1:
        brand = matched[0]
        rest = normalized
        for w in normalize_vehicle_text(brand.name).split():
            rest = re.sub(_word_boundary_pattern(w), " ", rest)
        rest = " ".join(rest.split()).strip()
        return brand, rest
    return None, text


def detect_model(text: str, brand: object, models_qs: QuerySet) -> Optional[object]:
    """
    Busca un solo modelo de la marca que aparezca como palabra completa en text.
    models_qs debe estar filtrado por brand. Retorna modelo o None si hay 0 o varias.
    """
    if not text or not models_qs.exists():
        return None
    normalized = normalize_vehicle_text(text)
    if not normalized:
        return None
    tokens = set(normalized.split())
    matched = []
    for model in models_qs:
        name_norm = normalize_vehicle_text(model.name)
        if not name_norm:
            continue
        model_words = name_norm.split()
        if all(w in tokens for w in model_words):
            matched.append(model)
    if len(matched) == 1:
        return matched[0]
    return None


def is_vehicle_specific_product(product) -> bool:
    """
    True si el producto es candidato a tener compatibilidad vehicular:
    categoría con slug que contenga clf, ensamble-directo o direct-fit;
    y no es categoría universal (flexibles, colas, silenciador, resonador).
    """
    slug = (product.category.slug or "").lower()
    for part in UNIVERSAL_CATEGORY_SLUG_PARTS:
        if part in slug:
            return False
    for part in VEHICLE_CATEGORY_SLUG_PARTS:
        if part in slug:
            return True
    return False


def is_universal_product(product) -> bool:
    """True si el producto es claramente universal (no tocar)."""
    slug = (product.category.slug or "").lower()
    for part in UNIVERSAL_CATEGORY_SLUG_PARTS:
        if part in slug:
            return True
    return False


def parse_year_range(text: str) -> Tuple[int, int]:
    """
    Busca en text un rango de años tipo (1900-2100) o 1900-2100.
    Retorna (year_from, year_to) o (1900, 2100) por defecto.
    """
    if not text:
        return 1900, 2100
    # (1900-2100) o 1900-2100; años 4 dígitos
    m = re.search(r"\(?\s*(\d{4})\s*[-–]\s*(\d{4})\s*\)?", (text or "").strip())
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if 1900 <= y1 <= 2100 and 1900 <= y2 <= 2100 and y1 <= y2:
            return y1, y2
    return 1900, 2100


def parse_vehicle_applications(text: str, brands_qs: QuerySet) -> List[Tuple[object, Optional[object]]]:
    """
    Extrae todas las aplicaciones vehículo (marca, modelo) desde el texto.
    Soporta múltiples aplicaciones separadas por " / ", " y ", " and ".
    Retorna lista de (brand, model|None). model=None significa "toda la marca".
    Sin duplicados por (brand.id, model.id si model else None).
    """
    from apps.catalog.models import VehicleModel

    if not text or not brands_qs.exists():
        return []
    normalized = normalize_vehicle_text(text)
    if not normalized:
        return []
    segments = re.split(r"\s+/\s+|\s+y\s+|\s+and\s+", normalized, flags=re.IGNORECASE)
    seen = set()
    result = []
    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue
        brand, rest = detect_brand(segment, brands_qs)
        if not brand:
            continue
        models_qs = VehicleModel.objects.filter(brand=brand).order_by("name")
        model = detect_model(rest or segment, brand, models_qs)
        key = (brand.id, model.id if model else None)
        if key in seen:
            continue
        seen.add(key)
        result.append((brand, model))
    return result
