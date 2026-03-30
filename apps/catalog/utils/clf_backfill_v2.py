# -*- coding: utf-8 -*-
"""
Parser v2 para backfill de compatibilidad CLF / tipo original.

- Detecta marca/modelo desde name y sku con alias y normalización.
- Normaliza errores tipo CLFOO2 -> CLF002, CLFO36 -> CLF036.
- Clasifica: EXACTA (marca+modelo), BAJA (solo marca), DESCARTADO (código/medida).
- No inventa compatibilidades sin evidencia.
- Soporta múltiples marcas (ej. Hyundai Accent / Kia Rio).
"""
import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# VehicleBrand/VehicleModel importados dentro de funciones que los usan para evitar imports circulares


@dataclass
class DetectionResult:
    """Resultado del clasificador para un producto CLF."""

    detected_brand: Optional[str] = None
    detected_model: Optional[str] = None
    precision: Optional[str] = None  # ALTA | BAJA | None
    action: str = "descartado"  # crear | descartado
    reason: str = ""
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    # Múltiples aplicaciones: (brand_name, model_name o None para "todos")
    applications: List[Tuple[str, Optional[str]]] = field(default_factory=list)


BRAND_ALIASES = {
    "audi": "Audi",
    "bmw": "BMW",
    "chevrolet": "Chevrolet",
    "chevy": "Chevrolet",
    "peugeot": "Peugeot",
    "renault": "Renault",
    "honda": "Honda",
    "hyundai": "Hyundai",
    "kia": "Kia",
    "nissan": "Nissan",
    "toyota": "Toyota",
    "mazda": "Mazda",
    "suzuki": "Suzuki",
    "ford": "Ford",
    "volkswagen": "Volkswagen",
    "vw": "Volkswagen",
    "citroen": "Citroen",
    "citroën": "Citroen",
    "fiat": "Fiat",
    "opel": "Opel",
    "seat": "Seat",
    "mercedes": "Mercedes-Benz",
    "mercedes-benz": "Mercedes-Benz",
}

GENERIC_NON_VEHICLE_TOKENS = {
    "clf",
    "cat",
    "tipo",
    "original",
    "euro",
    "plug",
    "play",
    "2",
    "2.0",
    "2.25",
    "2.5",
    "3",
    "200",
    "225",
    "250",
    "300",
    "convertidor",
    "catalitico",
    "cataliticos",
    "ensamble",
    "directo",
}


def strip_accents(text: str) -> str:
    """Quita acentos; NFKD y elimina caracteres combinables."""
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c))


def normalize_spaces(text: str) -> str:
    """Colapsa espacios múltiples en uno."""
    return " ".join((text or "").strip().split())


def normalize_text(text: str) -> str:
    """Minúsculas, sin acentos, / - _ a espacio, espacios colapsados."""
    text = strip_accents(text).lower()
    text = text.replace("/", " ")
    text = text.replace("-", " ")
    text = text.replace("_", " ")
    return normalize_spaces(text)


def normalize_sku_noise(text: str) -> str:
    """
    Corrige patrones frecuentes de OCR/carga:
    - CLFOO2 -> CLF002
    - CLFO36 -> CLF036
    - múltiples O en bloque numérico -> 0
    """
    raw = (text or "").upper().strip()
    raw = raw.replace("CLFOO", "CLF00")
    raw = raw.replace("CLFO", "CLF0")
    raw = re.sub(r"\bCLF\s+OO", "CLF00", raw)
    raw = re.sub(r"\bCLF\s+O", "CLF0", raw)
    return raw


def cleaned_candidate_text(name: str, sku: str) -> str:
    """Nombre + SKU normalizado, sin códigos técnicos que contaminen detección."""
    sku_norm = normalize_sku_noise(sku or "")
    combined = f"{name or ''} {sku_norm}"
    text = normalize_text(combined)
    # Quitar códigos tipo CLF001, CAT-HY01, números sueltos
    text = re.sub(r"\bclf\s*\d+\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bcat\s*[a-z]*\d*\b", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+(?:[.,]\d+)?\b", " ", text)
    return normalize_spaces(text)


def detect_brand(text: str) -> Optional[str]:
    """Devuelve la marca canónica si hay exactamente una en el texto."""
    matches = []
    for alias, canonical in BRAND_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            matches.append(canonical)
    matches = list(dict.fromkeys(matches))
    if len(matches) == 1:
        return matches[0]
    return None


def detect_all_brands(text: str) -> List[str]:
    """Devuelve lista de marcas canónicas encontradas en el texto (sin duplicados, orden aparición)."""
    seen = {}
    for alias, canonical in BRAND_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", text):
            seen[canonical] = True
    return list(seen.keys())


def detect_model_for_brand(text: str, brand_name: str) -> Optional[str]:
    """
    Busca el modelo más probable usando VehicleModel de la marca detectada.
    Match por frase exacta o por intersección de tokens.
    """
    if not brand_name:
        return None
    from apps.catalog.models import VehicleBrand, VehicleModel

    brand = VehicleBrand.objects.filter(name__iexact=brand_name).first()
    if not brand:
        return None
    models = list(VehicleModel.objects.filter(brand=brand).values_list("name", flat=True))
    if not models:
        return None

    text_norm = normalize_text(text)
    text_tokens = set(text_norm.split())
    best_model = None
    best_score = 0

    for model_name in models:
        model_norm = normalize_text(model_name)
        if not model_norm:
            continue
        model_tokens = set(model_norm.split())
        if not model_tokens:
            continue
        if re.search(rf"\b{re.escape(model_norm)}\b", text_norm):
            score = 100 + len(model_tokens)
        else:
            overlap = len(model_tokens & text_tokens)
            if overlap == 0:
                continue
            score = overlap
        if score > best_score:
            best_score = score
            best_model = model_name
    return best_model


def looks_like_technical_only(text: str) -> bool:
    """True si el texto parece solo código/medida, sin evidencia de vehículo."""
    tokens = [t for t in (text or "").split() if t]
    if not tokens:
        return True
    useful = [t for t in tokens if t not in GENERIC_NON_VEHICLE_TOKENS]
    if not useful:
        return True
    alpha_tokens = [t for t in useful if re.search(r"[a-z]", t)]
    return len(alpha_tokens) == 0


def extract_year_range(text: str) -> Tuple[int, int]:
    """
    Extrae rango de años del texto. Soporta:
    - (2013-2026) o (2013 - 2026)
    - 2010 al 2018 / 2010 a 2018
    - 2008-2015 / 2008 – 2015
    Si no encuentra nada, retorna (1900, 2100).
    """
    if not text:
        return 1900, 2100
    raw = (text or "").strip()
    # (2013-2026) o 2013-2026 con guión normal o en-dash
    m = re.search(r"\(?\s*(\d{4})\s*[-–]\s*(\d{4})\s*\)?", raw)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if 1900 <= y1 <= 2100 and 1900 <= y2 <= 2100 and y1 <= y2:
            return y1, y2
    # 2010 al 2018 / 2010 a 2018
    m = re.search(r"(\d{4})\s+(?:al|a)\s+(\d{4})", raw, re.IGNORECASE)
    if m:
        y1, y2 = int(m.group(1)), int(m.group(2))
        if 1900 <= y1 <= 2100 and 1900 <= y2 <= 2100 and y1 <= y2:
            return y1, y2
    return 1900, 2100


def classify_clf_product(name: str, sku: str) -> DetectionResult:
    """
    Clasifica un producto CLF por nombre y SKU.

    Reglas:
    - Solo código/medida -> action=descartado, reason=solo_codigo_o_medida
    - Sin marca única (0 o 2+ marcas sin soporte multi) -> action=descartado, reason=sin_marca_unica o demasiadas_marcas
    - Marca + modelo -> precision=ALTA, action=crear
    - Solo marca -> precision=BAJA, action=crear, detected_model=(todos)
    - Hasta 2 marcas con modelo o "todos" -> action=crear, applications lista de (brand, model|None)
    """
    combined_raw = f"{name or ''} {sku or ''}"
    year_from, year_to = extract_year_range(combined_raw)
    text = cleaned_candidate_text(name, sku)

    if not text or looks_like_technical_only(text):
        return DetectionResult(
            action="descartado",
            reason="solo_codigo_o_medida",
            year_from=year_from,
            year_to=year_to,
        )

    brands = detect_all_brands(text)

    if len(brands) == 0:
        return DetectionResult(
            action="descartado",
            reason="sin_marca_unica",
            year_from=year_from,
            year_to=year_to,
        )

    if len(brands) > 2:
        return DetectionResult(
            action="descartado",
            reason="demasiadas_marcas",
            year_from=year_from,
            year_to=year_to,
        )

    applications = []
    has_any_model = False
    for brand in brands:
        model = detect_model_for_brand(text, brand)
        if model:
            has_any_model = True
        applications.append((brand, model))

    precision = "ALTA" if has_any_model else "BAJA"
    reason = "marca_y_modelo_detectados" if has_any_model else "solo_marca_detectada"
    if len(applications) > 1:
        reason = "multi_marca_" + reason

    # Para compatibilidad con CSV
    detected_brand_str = "; ".join(a[0] for a in applications)
    detected_model_str = "; ".join(a[1] or "(todos)" for a in applications)

    return DetectionResult(
        detected_brand=detected_brand_str,
        detected_model=detected_model_str,
        precision=precision,
        action="crear",
        reason=reason,
        year_from=year_from,
        year_to=year_to,
        applications=applications,
    )
