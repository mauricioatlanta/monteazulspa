# -*- coding: utf-8 -*-
"""
Servicio de parsing y construcción de queryset para búsqueda mecánica de escapes.

Acepta consultas como: 2 x 8, 2.5 x 6, 2x6, 2X6, silenciador 2, 2 pulgadas, cola 2, renault clio.
Devuelve (ParsedEscapeQuery, QuerySet) listos para la vista de búsqueda.
"""
import re
import unicodedata
from decimal import Decimal
from dataclasses import dataclass
from typing import Optional, Tuple, List

from django.db.models import Q

from apps.catalog.models import Product, SearchLog
from apps.catalog.utils.engine_query_parser import parse_engine_query
from apps.catalog.services.vehicle_recommendation_rules import apply_engine_filter


# Diámetro (opcional pulg/pulgadas/") y opcional "x" o "X" + largo
INCH_PATTERN = re.compile(
    r'(?P<diam>\d+(?:[.,]\d+)?)\s*(?:"|pulg(?:adas)?\.?|in\.?)?(?:\s*[xX×]\s*(?P<length>\d+(?:[.,]\d+)?))?'
)
# Fracción 1/2, 1/4 etc. para normalizar a decimal
FRACTION_PATTERN = re.compile(r'(\d+)\s*/\s*(\d+)')

PRODUCT_KIND_KEYWORDS = {
    "flexible": ["flexible", "flex", "tubo flexible"],
    "silenciador": ["silenciador", "muffler"],
    "resonador": ["resonador", "resonator"],
    "cola": ["cola", "cola escape", "punta escape", "punta"],
    "catalitico": ["catalitico", "catalizador", "convertidor"],
}

# Slugs de categorías que existen en el proyecto (varios por tipo para legacy/canonical).
CATEGORY_SLUG_MAP = {
    "flexible": [
        "flexibles",
        "flexibles-reforzados",
        "flexibles-normales",
        "flexibles-con-extension",
    ],
    "silenciador": [
        "silenciadores-alto-flujo",
        "silenciadores",
        "silenciadores-de-alto-flujo",
        "silenciador-linea-dw",
        "silenciador-alto-flujo-lt",
    ],
    "resonador": [
        "resonadores",
        "resonador-deportivo-alto-flujo-ltm",
    ],
    "cola": [
        "colas-de-escape",
        "colas_de_escape",
    ],
    "catalitico": [
        "convertidores-cataliticos",
        "cataliticos-ensamble-directo",
        "cataliticos",
        "cataliticos-twg",
        "cataliticos-clf",
    ],
}


@dataclass
class ParsedEscapeQuery:
    raw: str
    normalized: str
    search_type: str  # "measure" | "vehicle" | "mixed" | "unknown"
    product_kind: Optional[str] = None
    diameter_in: Optional[Decimal] = None
    length_in: Optional[Decimal] = None
    length_mm: Optional[int] = None


def _normalize_fractions(text: str) -> str:
    """Convierte '2 1/2' -> '2.5', '1/2' -> '0.5' dentro del texto."""
    def replace_frac(m):
        a, b = int(m.group(1)), int(m.group(2))
        if b == 0:
            return m.group(0)
        return str(round(a / b, 2) if a % b else a // b)
    return FRACTION_PATTERN.sub(replace_frac, text)


def normalize_search_query(text: str) -> str:
    """
    Normaliza la consulta para mejorar el matching:
    - Minúsculas, sin tildes, espacios colapsados
    - Coma decimal -> punto (2,5 -> 2.5)
    - "pulgadas", "pulg", "pulg.", " in", '"' -> espacio para que el número quede limpio
    - Fracciones 1/2, 1/4 -> decimal (2 1/2 -> 2.5)
    """
    if not text:
        return ""
    s = (text or "").strip().lower()
    # Quitar tildes (opcional pero ayuda: "pulgadas" ya está en minúsculas)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Coma entre dígitos -> punto
    s = re.sub(r"(\d),(\d)", r"\1.\2", s)
    # Palabras/unidades que siguen a un número: quitar para no romper el número
    s = re.sub(r"\bpulgadas?\b\.?", " ", s, flags=re.IGNORECASE)
    s = re.sub(r"\bin\.?", " ", s, flags=re.IGNORECASE)
    s = re.sub(r'"', " ", s)
    # Fracciones: 2 1/2 -> 2.5
    s = _normalize_fractions(s)
    return " ".join(s.split())


def extract_product_kind(text: str) -> Optional[str]:
    """Detecta tipo de producto por palabras clave."""
    for kind, keywords in PRODUCT_KIND_KEYWORDS.items():
        if any(k in text for k in keywords):
            return kind
    return None


def extract_inches_and_length(text: str) -> Tuple[Optional[Decimal], Optional[Decimal], Optional[int]]:
    """Extrae diámetro (y opcionalmente largo) desde texto. Largo en pulg se convierte a mm."""
    match = INCH_PATTERN.search(text)
    if not match:
        return None, None, None

    diam_txt = match.group("diam")
    length_txt = match.group("length")

    diameter = Decimal(diam_txt.replace(",", ".")) if diam_txt else None
    length = Decimal(length_txt.replace(",", ".")) if length_txt else None
    length_mm = int(round(float(length) * 25.4)) if length is not None else None
    return diameter, length, length_mm


def detect_escape_search_type(
    normalized: str,
    diameter: Optional[Decimal],
    length: Optional[Decimal],
    product_kind: Optional[str],
) -> str:
    """Determina si la búsqueda es por medidas, por vehículo o desconocida."""
    if diameter is not None:
        return "measure"
    if product_kind == "catalitico":
        return "vehicle"
    words = normalized.split()
    if len(words) >= 2:
        return "vehicle"
    return "unknown"


def parse_escape_query(text: str) -> ParsedEscapeQuery:
    """Unifica normalización, tipo de producto, medidas y tipo de búsqueda."""
    normalized = normalize_search_query(text)
    product_kind = extract_product_kind(normalized)
    diameter, length, length_mm = extract_inches_and_length(normalized)
    search_type = detect_escape_search_type(normalized, diameter, length, product_kind)

    # Si hay largo y no se dijo tipo, asumir flexible
    if length is not None and product_kind is None:
        product_kind = "flexible"

    return ParsedEscapeQuery(
        raw=text,
        normalized=normalized,
        search_type=search_type,
        product_kind=product_kind,
        diameter_in=diameter,
        length_in=length,
        length_mm=length_mm,
    )


def build_escape_queryset(text: str) -> Tuple[ParsedEscapeQuery, "Product.QuerySet"]:
    """
    Construye el queryset de productos según la consulta parseada.
    Devuelve (parsed, qs) para que la vista muestre resultados e interpretación.
    """
    parsed = parse_escape_query(text)
    qs = (
        Product.objects.filter(deleted_at__isnull=True, is_active=True)
        .select_related("category")
    )

    if parsed.search_type == "vehicle":
        vehicle_q = (
            Q(name__icontains=parsed.normalized)
            | Q(sku__icontains=parsed.normalized.replace(" ", "-"))
            | Q(sku__icontains=parsed.normalized.replace(" ", ""))
            | Q(category__slug__in=CATEGORY_SLUG_MAP.get("catalitico", []))
        )
        qs = qs.filter(vehicle_q)

        # Afinar con heurísticas de motor (cc/fuel/year) con degradación suave.
        parsed_engine = parse_engine_query(text)
        is_relaxed = False
        if parsed_engine.cc or parsed_engine.fuel or parsed_engine.year:
            base_qs = qs
            filtered = apply_engine_filter(
                base_qs,
                cc=parsed_engine.cc,
                fuel=parsed_engine.fuel,
                year=parsed_engine.year,
            )
            strict_sample = list(filtered[:6])
            if len(strict_sample) < 5 and parsed_engine.year:
                filtered_relaxed = apply_engine_filter(
                    base_qs,
                    cc=parsed_engine.cc,
                    fuel=parsed_engine.fuel,
                    year=None,
                )
                relaxed_sample = list(filtered_relaxed[:6])
                if len(relaxed_sample) >= len(strict_sample):
                    qs = filtered_relaxed
                    is_relaxed = True
                else:
                    qs = filtered
            else:
                qs = filtered

        # Log específico de búsquedas de escape vehiculares / por motor.
        try:
            SearchLog.objects.create(
                query=text,
                cc=parsed_engine.cc,
                fuel=parsed_engine.fuel,
                year=parsed_engine.year,
                results_count=len(list(qs[:6])),
                is_relaxed=is_relaxed,
            )
        except Exception:
            pass

        return parsed, qs

    if parsed.product_kind:
        slugs: List[str] = CATEGORY_SLUG_MAP.get(parsed.product_kind, [])
        if slugs:
            qs = qs.filter(category__slug__in=slugs)

    if parsed.diameter_in is not None:
        qs = qs.filter(
            Q(diametro_entrada=parsed.diameter_in) | Q(diametro_salida=parsed.diameter_in)
        )

    if parsed.length_mm is not None:
        tolerance = 10
        qs = qs.filter(
            largo_mm__gte=parsed.length_mm - tolerance,
            largo_mm__lte=parsed.length_mm + tolerance,
        )

    if parsed.search_type == "unknown":
        qs = qs.filter(
            Q(name__icontains=parsed.normalized) | Q(sku__icontains=parsed.normalized)
        )

    # Afinar resultados por motor incluso en búsquedas por producto/marca libre, con degradación.
    parsed_engine = parse_engine_query(text)
    is_relaxed = False
    if parsed_engine.cc or parsed_engine.fuel or parsed_engine.year:
        base_qs = qs
        filtered = apply_engine_filter(
            base_qs,
            cc=parsed_engine.cc,
            fuel=parsed_engine.fuel,
            year=parsed_engine.year,
        )
        strict_sample = list(filtered[:6])
        if len(strict_sample) < 5 and parsed_engine.year:
            filtered_relaxed = apply_engine_filter(
                base_qs,
                cc=parsed_engine.cc,
                fuel=parsed_engine.fuel,
                year=None,
            )
            relaxed_sample = list(filtered_relaxed[:6])
            if len(relaxed_sample) >= len(strict_sample):
                qs = filtered_relaxed
                is_relaxed = True
            else:
                qs = filtered
        else:
            qs = filtered

    # Log genérico para escape search.
    try:
        SearchLog.objects.create(
            query=text,
            cc=parsed_engine.cc,
            fuel=parsed_engine.fuel,
            year=parsed_engine.year,
            results_count=len(list(qs[:6])),
            is_relaxed=is_relaxed,
        )
    except Exception:
        pass

    return parsed, qs
