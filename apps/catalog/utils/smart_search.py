"""
Parser reutilizable para el Buscador Inteligente de Escape.
Interpreta la query del usuario y determina si es medida, vehículo o producto.
"""
import re


# Normalización de acentos (construido por carácter para evitar problemas de encoding del archivo)
_ACCENT_PAIRS = [
    ("áàäâã", "a"), ("éèëê", "e"), ("íìïî", "i"), ("óòöôõ", "o"), ("úùüû", "u"), ("ñ", "n"),
]
_ACCENT_MAP = str.maketrans(
    "".join(t[0] for t in _ACCENT_PAIRS) + "".join(t[0].upper() for t in _ACCENT_PAIRS),
    "".join(t[1] * len(t[0]) for t in _ACCENT_PAIRS) + "".join(t[1].upper() * len(t[0]) for t in _ACCENT_PAIRS),
)


def _normalize_text_for_match(text):
    """Lower + collapse spaces + remove accents for matching."""
    if not text:
        return ""
    s = text.strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s.translate(_ACCENT_MAP)


def normalize_query(q):
    """
    Normaliza la query: lower, strip, colapsar espacios.
    No modifica comas/puntos para no destruir el texto original al mostrarlo.
    """
    if q is None:
        return ""
    s = str(q).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def parse_measure_query(q):
    """
    Detecta patrones de medida: 2x6, 2 x 6, 2*6, 2,5x8, flexible 2x6, silenciador 2.5 x 8.
    Retorna dict con matched, diametro, largo_pulg, largo_mm; si no coincide, matched=False.
    """
    if not q or not isinstance(q, str):
        return {"matched": False}

    # Para parseo numérico usamos punto; no alteramos el texto original para mostrar
    normalized = normalize_query(q)
    # Permitir coma como decimal solo en el patrón
    work = normalized.replace(",", ".")
    # Patrón: opcional prefijo (flexible, silenciador, etc.) + número + x o * + número
    match = re.search(
        r"(?:^|\s)(\d+(?:\.\d+)?)\s*[x*]\s*(\d+(?:\.\d+)?)(?:\s|$|[^\d])",
        work,
        re.IGNORECASE,
    )
    if not match:
        return {"matched": False}

    try:
        diametro_str = match.group(1).replace(",", ".")
        largo_pulg_str = match.group(2).replace(",", ".")
        diametro_val = float(diametro_str)
        largo_pulg_val = float(largo_pulg_str)
        largo_mm = int(round(largo_pulg_val * 25.4))
        d_str = str(diametro_val) if diametro_val != int(diametro_val) else str(int(diametro_val))
        l_str = str(largo_pulg_val) if largo_pulg_val != int(largo_pulg_val) else str(int(largo_pulg_val))
        return {
            "matched": True,
            "diametro": d_str,
            "largo_pulg": l_str,
            "largo_mm": str(largo_mm),
        }
    except (ValueError, TypeError):
        return {"matched": False}


def detect_year(q):
    """Detecta un año de 4 dígitos razonable (1950-2035). Retorna int o None."""
    if not q or not isinstance(q, str):
        return None
    matches = re.findall(r"\b(19[5-9]\d|20[0-2]\d|203[0-5])\b", q)
    if not matches:
        return None
    return int(matches[0])


def _name_as_word_pattern(name_norm):
    """Patrón regex para que el nombre aparezca como palabra (límites no-alfanuméricos o inicio/fin)."""
    escaped = re.escape(name_norm)
    return re.compile(r"(?:^|[\s\W])" + escaped + r"(?:[\s\W]|$)", re.IGNORECASE)


def detect_brand_model(q):
    """
    Usa BD: VehicleBrand, VehicleModel.
    Busca marcas/modelos cuyo nombre aparezca como palabra en el texto (límites para evitar falsos positivos).
    Si hay marca, prioriza modelos de esa marca. Case-insensitive, prioriza coincidencias más largas.
    Retorna {"brand": {"id", "name"}|None, "model": {"id", "name", "brand_id"}|None} sin get() extra.
    """
    from apps.catalog.models import VehicleBrand, VehicleModel

    if not q or not isinstance(q, str):
        return {"brand": None, "model": None}

    text_norm = _normalize_text_for_match(q)
    if not text_norm:
        return {"brand": None, "model": None}

    MIN_LEN = 2

    brands = list(VehicleBrand.objects.all().order_by("name").values("id", "name"))
    brand_found = None
    best_brand_len = 0
    for b in brands:
        name_norm = _normalize_text_for_match(b["name"])
        if len(name_norm) < MIN_LEN:
            continue
        if _name_as_word_pattern(name_norm).search(text_norm) and len(name_norm) > best_brand_len:
            brand_found = b
            best_brand_len = len(name_norm)

    if brand_found:
        models_qs = VehicleModel.objects.filter(brand_id=brand_found["id"]).order_by("name")
    else:
        models_qs = VehicleModel.objects.order_by("name")

    models_list = list(models_qs.values("id", "name", "brand_id"))
    model_found = None
    best_model_len = 0
    for m in models_list:
        name_norm = _normalize_text_for_match(m["name"])
        if len(name_norm) < MIN_LEN:
            continue
        if _name_as_word_pattern(name_norm).search(text_norm) and len(name_norm) > best_model_len:
            if brand_found and m["brand_id"] != brand_found["id"]:
                continue
            model_found = m
            best_model_len = len(name_norm)

    return {"brand": brand_found, "model": model_found}


# Términos que sugieren intención vehicular cuando aparecen junto a marca/modelo/año
VEHICLE_HINT_WORDS = frozenset(
    _normalize_text_for_match(w)
    for w in (
        "catalitico",
        "catalítico",
        "escape",
        "silenciador",
        "resonador",
        "cola",
        "flexible",
    )
)


def parse_smart_search(q):
    """
    Determina tipo: "measure" | "vehicle" | "product" | "empty".
    Reglas: vacío => empty; parse_measure_query match => measure;
    si detecta marca/modelo/año con semántica vehicular => vehicle; si no => product.
    Retorna dict con: original_query, normalized_query, type, measure, brand_id, brand_name,
    model_id, model_name, year, product_query.
    """
    original = (q or "").strip()
    normalized = normalize_query(original)

    if not normalized:
        return {
            "original_query": original,
            "normalized_query": normalized,
            "type": "empty",
            "measure": None,
            "brand_id": None,
            "brand_name": None,
            "model_id": None,
            "model_name": None,
            "year": None,
            "product_query": original,
        }

    measure = parse_measure_query(normalized)
    if measure.get("matched"):
        return {
            "original_query": original,
            "normalized_query": normalized,
            "type": "measure",
            "measure": measure,
            "brand_id": None,
            "brand_name": None,
            "model_id": None,
            "model_name": None,
            "year": None,
            "product_query": original,
        }

    year = detect_year(normalized)
    brand_model = detect_brand_model(normalized)
    brand = brand_model.get("brand")
    model = brand_model.get("model")
    text_norm = _normalize_text_for_match(normalized)
    has_vehicle_hint = any(h in text_norm for h in VEHICLE_HINT_WORDS)

    # Vehicle solo si hay marca o modelo, o si hay año y además pista vehicular (ej. toyota 2015 sí; 2015 solo no)
    has_vehicle_data = (brand is not None or model is not None) or (year is not None and has_vehicle_hint)

    if has_vehicle_data:
        return {
            "original_query": original,
            "normalized_query": normalized,
            "type": "vehicle",
            "measure": None,
            "brand_id": brand["id"] if brand else None,
            "brand_name": brand["name"] if brand else None,
            "model_id": model["id"] if model else None,
            "model_name": model["name"] if model else None,
            "year": year,
            "product_query": original,
        }

    # Por defecto: búsqueda por producto/categoría
    return {
        "original_query": original,
        "normalized_query": normalized,
        "type": "product",
        "measure": None,
        "brand_id": None,
        "brand_name": None,
        "model_id": None,
        "model_name": None,
        "year": None,
        "product_query": original,
    }


# --- Validación manual (Buscador Inteligente) ---
# 1. /productos/buscar/?q=2x6
#    => Redirige a /productos/buscar-escape/?q=2x6
# 2. /productos/buscar/?q=2,5x8
#    => Redirige a /productos/buscar-escape/?q=2,5x8
# 3. /productos/buscar/?q=toyota yaris 2015
#    => Redirige a /productos/buscador-vehiculo/?q=...&brand_id=...&model_id=...&year=2015
#    con selects precargados y búsqueda automática al cargar.
# 4. /productos/buscar/?q=catalitico toyota yaris
#    => Redirige a búsqueda por vehículo si se detecta marca/modelo.
# 5. /productos/buscar/?q=silenciador alto flujo
#    => Redirige a /productos/?q=silenciador alto flujo (listado general).
# 6. /productos/buscar/?q=2015
#    => Redirige a listado producto (solo año sin marca/modelo/hint no es vehicle).
# 7. /productos/buscar/?q=yaris
#    => Si solo viene model_id, vehicle_search_page infiere marca y precarga initial_models.
