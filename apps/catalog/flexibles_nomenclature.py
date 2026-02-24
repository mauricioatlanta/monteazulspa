# -*- coding: utf-8 -*-
"""
Nomenclatura oficial de flexibles según lista de precios (imagen/documento).

- FLEXIBLE PIPE WITH INNER BRAID REFORZADO: medidas en formato "N X M" (espacio X espacio).
- flex reforzado with napples: 2 X 6 y 2 X 8 (productos con extensión/nipple).

Se usa para nombres en catálogo sin modificar precios.
"""
import re

# SKU normalizado (para búsqueda) -> nombre para catálogo (nomenclatura de la lista)
# Lista según tabla de precios: FLEXIBLES REFORZADOS
FLEXIBLES_INNER_BRAID_NOMENCLATURE = {
    "1.75X4": "1.75 X 4",
    "1.75X6": "1.75 X 6",
    "1.75X8": "1.75 X 8",
    "1.75X10": "1.75 X 10",
    "1.75X12": "1.75 X 12",
    "2X4": "2 X 4",
    "2X6": "2 X 6",
    "2X8": "2 X 8",
    "2X10": "2 X 10",
    "2.5X6": "2.5 X 6",
    "2.5X8": "2.5 X 8",
    "3X4": "3 X 4",
    "170X10": "1.75 X 10",  # 170 = 1.75 (notación manuscrita)
    "3X6": "3 X 6",
    "3X8": "3 X 8",
    "4X6": "4 X 6",
    "4X8": "4 X 8",
    "12X10": "12 X 10",  # Medida 12x10 (verificar si es 1.2x10 en algunos contextos)
}

# Flex reforzado with napples (con nipple/extensión/caño): SKU del producto -> nombre catálogo
FLEXIBLES_NIPPLES_NOMENCLATURE = {
    "2X6EXT-REF": "Flex reforzado con extensión 2 X 6",
    "2X8EXT-REF": "Flex reforzado con extensión 2 X 8",
    "2.5X6EXT-REF": "Flex reforzado con extensión 2.5 X 6",
}

# Todos los SKU de inner braid (lista de modelos de la imagen)
FLEXIBLES_INNER_BRAID_SKUS = tuple(FLEXIBLES_INNER_BRAID_NOMENCLATURE.keys())


def normalize_measure_to_sku(val):
    """Convierte medida (ej. '2,5 X 6', '1.75 X 8', '1.75-X-8', '2-X-4') a SKU: 2.5X6, 1.75X8."""
    if val is None or (isinstance(val, str) and not str(val).strip()):
        return ""
    s = str(val).strip().upper()
    s = s.replace(",", ".")
    # Unificar separador: espacios o guiones alrededor de X -> una sola X (1.75-X-8, 2 X 6, etc.)
    s = re.sub(r"[-\s]*[xX][-\s]*", "X", s)
    s = re.sub(r"\s+", "", s)[:50]
    return s


def get_display_name_for_sku(sku, include_suffix=False, suffix=" Reforzado"):
    """
    Devuelve el nombre de catálogo para un flexible según la nomenclatura de la lista.
    - Si sku está en inner braid: "1.75 X 6", "2.5 X 6", etc.
    - Si sku está en nipples: "Flex reforzado con nipple 2 X 6".
    - Si no está en ningún mapa: None (no se fuerza nombre).
    """
    if not sku:
        return None
    key = normalize_measure_to_sku(sku)
    name = FLEXIBLES_INNER_BRAID_NOMENCLATURE.get(key) or FLEXIBLES_NIPPLES_NOMENCLATURE.get(
        (sku or "").strip().upper()
    )
    if name and include_suffix and key in FLEXIBLES_INNER_BRAID_NOMENCLATURE:
        name = (name + suffix)[:255]
    return name


def parse_flexible_measure_from_sku(sku):
    """
    Parsea el SKU de un flexible y devuelve (diam_pulg, largo_pulg) en formato float
    para mostrar en especificaciones, o None si no se puede interpretar.

    Ejemplos: "25x6" -> (2.5, 6), "175x6" -> (1.75, 6), "2X6" -> (2, 6), "2.5X8" -> (2.5, 8).
    Convención: "25" sin decimal = 2.5 pulgadas, "175" = 1.75 pulgadas.
    """
    if not sku or not isinstance(sku, str):
        return None
    key = normalize_measure_to_sku(sku)
    if not key or "X" not in key:
        return None
    parts = key.split("X", 1)
    if len(parts) != 2:
        return None
    try:
        d_raw = parts[0].strip()
        l_raw = parts[1].strip()
        # Quitar sufijos no numéricos (ej. 6EXT-REF -> 6)
        l_raw = re.sub(r"[^0-9.,].*$", "", l_raw)
        if not l_raw:
            return None
        # Diámetro: 25 -> 2.5, 175 -> 1.75
        if d_raw == "25":
            diam = 2.5
        elif d_raw == "175":
            diam = 1.75
        else:
            diam = float(d_raw.replace(",", "."))
        largo = float(l_raw.replace(",", "."))
        if diam <= 0 or largo <= 0:
            return None
        return (diam, largo)
    except (ValueError, TypeError):
        return None


def get_flexible_dimensions_display(sku):
    """
    Devuelve texto explicativo de dimensiones para flexibles, para mostrar en ficha/especificaciones.
    Ej: '2.5" x 6" (diámetro x largo en pulgadas)'.
    Si el SKU no corresponde a una medida de flexible, devuelve None.
    """
    parsed = parse_flexible_measure_from_sku(sku)
    if not parsed:
        return None
    diam, largo = parsed
    # Formatear sin decimales innecesarios (2.0 -> 2)
    d_str = str(diam) if diam != int(diam) else str(int(diam))
    l_str = str(largo) if largo != int(largo) else str(int(largo))
    return f'{d_str}" x {l_str}" (diámetro x largo en pulgadas)'
