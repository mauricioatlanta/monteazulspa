"""
Sugerencias para autocomplete del Buscador Inteligente.
Usa BD real (VehicleBrand, VehicleModel, Product, Category); sin listas hardcodeadas grandes.
"""
import re
from django.urls import reverse
from django.utils.http import urlencode
from apps.catalog.public_visibility import exclude_removed_categories, exclude_removed_products

# Misma normalización de acentos que smart_search (evitar dependencia circular)
_ACCENT_PAIRS = [
    ("áàäâã", "a"), ("éèëê", "e"), ("íìïî", "i"), ("óòöôõ", "o"), ("úùüû", "u"), ("ñ", "n"),
]
_ACCENT_MAP = str.maketrans(
    "".join(t[0] for t in _ACCENT_PAIRS) + "".join(t[0].upper() for t in _ACCENT_PAIRS),
    "".join(t[1] * len(t[0]) for t in _ACCENT_PAIRS)
    + "".join(t[1].upper() * len(t[0]) for t in _ACCENT_PAIRS),
)


def normalize_query(q):
    """Lower, strip, colapsar espacios, normalizar acentos (robusto como smart_search)."""
    if q is None:
        return ""
    s = str(q).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s.translate(_ACCENT_MAP)


def build_suggestion(label, type, query_text):
    """Construye un item de sugerencia con label, type, query y url al smart_search."""
    base = reverse("catalog:smart_search")
    url = base + "?" + urlencode({"q": query_text})
    return {
        "label": label,
        "type": type,
        "query": query_text,
        "url": url,
    }


def _vehicle_match_score(label_norm, q_norm):
    """Puntuación: exacto=3, startswith=2, substring=1, sino 0."""
    if not label_norm or not q_norm:
        return 0
    if label_norm == q_norm:
        return 3
    if label_norm.startswith(q_norm):
        return 2
    if q_norm in label_norm:
        return 1
    return 0


def get_vehicle_suggestions(q, limit=4):
    """
    Sugerencias de marcas y modelos desde BD, con ranking: exacto > startswith > substring.
    Query corta: marcas antes que combinaciones. Query que coincide con modelo: combinaciones antes que marcas.
    """
    from apps.catalog.models import VehicleBrand, VehicleModel

    q = (q or "").strip()
    if not q or len(q) < 2:
        return []

    q_norm = normalize_query(q)
    short_query = len(q_norm) <= 2
    scored = []

    # Marcas
    brands = list(
        VehicleBrand.objects.all().order_by("name").values("id", "name")[: limit * 3]
    )
    for b in brands:
        name = b["name"] or ""
        name_norm = normalize_query(name)
        score = _vehicle_match_score(name_norm, q_norm)
        if score > 0:
            scored.append((score, True, False, name))

    # Modelos: "Marca Modelo"
    models_qs = (
        VehicleModel.objects.filter(brand__isnull=False)
        .order_by("brand__name", "name")
        .values("id", "name", "brand__name")[: limit * 4]
    )
    for m in models_qs:
        brand_name = m["brand__name"] or ""
        model_name = m["name"] or ""
        label_combo = f"{brand_name} {model_name}".strip()
        if not label_combo:
            continue
        label_norm = normalize_query(label_combo)
        model_norm = normalize_query(model_name)
        score = _vehicle_match_score(label_norm, q_norm)
        if score == 0:
            continue
        model_matches = (
            model_norm == q_norm
            or model_norm.startswith(q_norm)
            or q_norm in model_norm
        )
        scored.append((score, False, model_matches, label_combo))

    # Ordenar: score desc; si query corta, marcas primero; si no corta y model_matches, combos primero
    def sort_key(item):
        score, is_brand, model_matches, label = item
        secondary = 1
        if short_query and is_brand:
            secondary = 0
        elif not short_query and model_matches and not is_brand:
            secondary = 0
        return (-score, secondary, label)

    scored.sort(key=sort_key)

    seen = set()
    out = []
    for _, _, _, label in scored:
        if len(out) >= limit:
            break
        key = label.lower().strip()
        if key not in seen:
            seen.add(key)
            out.append(build_suggestion(label, "vehicle", label))

    return out[:limit]


def get_measure_suggestions(q, limit=3):
    """
    Sugerencias de medidas desde Product (diametro_entrada/salida, largo_mm).
    Formato: 2x6, 2.5x8, Flexible 2x6. Fallback con medidas frecuentes si la BD da poco.
    """
    from apps.catalog.models import Product
    from decimal import Decimal

    q = (q or "").strip()
    q_lower = q.lower()

    def _largo_mm_to_pulg(largo_mm):
        if largo_mm is None:
            return None
        return round(int(largo_mm) / 25.4, 1)

    def _format_measure(diam, largo_pulg):
        if diam is None or largo_pulg is None:
            return None
        d_str = str(int(diam)) if diam == int(diam) else str(float(diam))
        l_str = str(int(largo_pulg)) if largo_pulg == int(largo_pulg) else str(float(largo_pulg))
        return f"{d_str}x{l_str}"

    out = []
    seen = set()
    q_norm = normalize_query(q) if q else ""

    # Medidas reales desde productos activos (diámetro x largo en pulgadas)
    rows = (
        exclude_removed_products(
            Product.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
        )
        .exclude(diametro_entrada__isnull=True)
        .exclude(largo_mm__isnull=True)
        .values_list("diametro_entrada", "largo_mm")
        .distinct()[:20]
    )
    for diam, largo_mm in rows:
        if len(out) >= limit:
            break
        try:
            lp = _largo_mm_to_pulg(largo_mm)
            label = _format_measure(Decimal(str(diam)), lp)
            if not label or label in seen:
                continue
            if q_norm and q_norm not in label.replace(".", "").replace(",", "").lower():
                continue
            seen.add(label)
            out.append(build_suggestion(label, "measure", label))
        except (TypeError, ValueError):
            continue

    # Opcional: variante "Flexible 2x6" si ya tenemos "2x6" y el usuario escribió "flex" o similar
    if len(out) < limit and q_lower.startswith("flex"):
        for i, s in enumerate(list(out)):
            if s["label"].replace(".", "").replace("x", "").isdigit() or "x" in s["label"]:
                flex_label = "Flexible " + s["label"]
                if flex_label not in seen:
                    seen.add(flex_label)
                    out.insert(i + 1, build_suggestion(flex_label, "measure", flex_label))
                    break
        out = out[:limit]

    # Fallback: medidas frecuentes si no hay suficientes desde BD
    if len(out) < limit:
        fallback = [("2", 6), ("2", 8), ("2.5", 8), ("3", 6)]
        for d, l in fallback:
            if len(out) >= limit:
                break
            label = f"{d}x{l}"
            if label in seen:
                continue
            if q_norm and q_norm not in label.replace(".", "").lower():
                continue
            seen.add(label)
            out.append(build_suggestion(label, "measure", label))

    return out[:limit]


def get_product_suggestions(q, limit=4):
    """
    Sugerencias desde categorías y productos (nombres).
    Ejemplos: Catalítico, Silenciador alto flujo, Resonador deportivo.
    """
    from apps.catalog.models import Category, Product

    q = (q or "").strip()
    if not q or len(q) < 2:
        return []

    q_norm = normalize_query(q)
    seen = set()
    out = []

    # Categorías activas cuyo nombre coincida (fetch razonable y filtrar por q_norm)
    cats = list(
        exclude_removed_categories(Category.objects.filter(is_active=True)).values_list("name", flat=True)[:50]
    )
    for name in cats:
        if len(out) >= limit:
            break
        if not name:
            continue
        if q_norm in normalize_query(name):
            key = name.lower().strip()
            if key not in seen:
                seen.add(key)
                out.append(build_suggestion(name, "product", name))

    # Productos cuyo nombre coincida
    products = list(
        exclude_removed_products(
            Product.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
        )
        .values_list("name", flat=True)[:50]
    )
    for name in products:
        if len(out) >= limit:
            break
        if not name:
            continue
        if q_norm in normalize_query(name):
            key = name.lower().strip()
            if key not in seen:
                seen.add(key)
                out.append(build_suggestion(name, "product", name))

    return out[:limit]


def get_smart_search_suggestions(q, total_limit=8):
    """
    Combina vehicle, measure y product; máximo total_limit, sin duplicados por label.
    Mínimo 2 caracteres en general; excepción: 1 carácter si es dígito (ej. "2", "3") para sugerir medidas.
    Si q parece medida (empieza por número o contiene 'x'), prioriza measure.
    Si hay coincidencias de vehículo, prioriza vehicle.
    """
    q = (q or "").strip()
    if len(q) < 2:
        if len(q) == 1 and q[0].isdigit():
            pass
        else:
            return []

    q_norm = normalize_query(q)
    looks_like_measure = bool(re.match(r"^\d", q_norm)) or "x" in q_norm

    # Cuotas por tipo (ajustables para no pasarse de total_limit)
    n_vehicle = 4
    n_measure = 3
    n_product = 4

    vehicle = get_vehicle_suggestions(q, limit=n_vehicle)
    measure = get_measure_suggestions(q, limit=n_measure)
    product = get_product_suggestions(q, limit=n_product)

    # Orden de prioridad según contexto
    if looks_like_measure:
        ordered = measure + vehicle + product
    elif vehicle:
        ordered = vehicle + measure + product
    else:
        ordered = measure + vehicle + product

    seen_labels = set()
    results = []
    for s in ordered:
        if len(results) >= total_limit:
            break
        key = (s["label"] or "").strip().lower()
        if key and key not in seen_labels:
            seen_labels.add(key)
            results.append(s)

    return results[:total_limit]


# --- Validación manual (sugerencias) ---
# Casos a probar en el input del header:
#   ya   -> sugerencias vehículo (Yaris, etc.); ranking: combos que coincidan con modelo primero
#   toy  -> Toyota, Toyota Yaris, etc.; ranking: exacto > startswith > substring; marcas antes si query corta
#   2    -> medidas (excepción 1 dígito: sí sugiere)
#   3    -> medidas (excepción 1 dígito)
#   a, t -> nada (mínimo 2 caracteres salvo dígito)
#   2x   -> medidas que empiecen o contengan 2x
#   sil  -> Silenciador, silenciador alto flujo, etc.
#   cat  -> Catalítico, categorías/productos con "cat"
