from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from apps.catalog.services.technical_rules import _norm_fuel
from apps.catalog.utils.smart_search import detect_year


@dataclass
class ParsedEngineQuery:
    """
    Representa una interpretación simple de una query de motor.

    Ejemplos de textos soportados:
    - "toyota hilux 2.4 diesel 2018"
    - "2.0 gasolina 2015"
    - "hilux 3000cc diesel"
    """

    cc: Optional[int] = None
    fuel: Optional[str] = None
    year: Optional[int] = None


def _normalize_text(text: str) -> str:
    return (text or "").strip().lower()


def _detect_fuel(text: str) -> Optional[str]:
    """
    Detecta combustible desde texto libre y lo normaliza con _norm_fuel.
    """
    if not text:
        return None
    t = _normalize_text(text)

    # Marcas diésel comunes en texto libre
    if "tdi" in t or "hdi" in t or re.search(r"\bdiesel\b", t):
        return _norm_fuel("DIESEL") or "DIESEL"
    if re.search(r"\b(gasolina|bencina|nafta)\b", t):
        return _norm_fuel("BENCINA") or "BENCINA"

    return None


def _detect_cc(text: str) -> Optional[int]:
    """
    Heurística simple para detectar cilindrada:

    - Números tipo 2.0, 2,4, 1.6 → litros → *1000.
    - Números enteros entre 600 y 8000 → cc directos (ej. 2000, 2400, 3000).
    """
    if not text:
        return None

    t = _normalize_text(text)
    # Permitir coma decimal
    numbers = re.findall(r"\d+(?:[.,]\d+)?", t)
    if not numbers:
        return None

    for raw in numbers:
        val_str = raw.replace(",", ".")
        try:
            val = float(val_str)
        except ValueError:
            continue

        # 0.6–8.0 → litros
        if 0.6 <= val <= 8.0:
            return int(float(val) * 1000)

        # Si es entero y "grande", asumir cc directos
        iv = int(round(val))
        if 600 <= iv <= 8000:
            return iv

    return None


def parse_engine_query(text: Optional[str]) -> ParsedEngineQuery:
    """
    Parser universal de query de motor para usar junto a apply_engine_filter.

    No toca base de datos; solo usa heurísticas sobre el texto:
    - Año: usa detect_year de smart_search.
    - Combustible: diesel / gasolina / bencina / nafta.
    - CC: litros (2.0, 2,4) o cc directos (2000, 2400).
    """
    if not text:
        return ParsedEngineQuery()

    s = _normalize_text(text)

    year = detect_year(s)
    fuel = _detect_fuel(s)
    cc = _detect_cc(s)

    return ParsedEngineQuery(cc=cc, fuel=fuel, year=year)


__all__ = ["ParsedEngineQuery", "parse_engine_query"]

