from __future__ import annotations

from typing import List, Optional


def _norm_fuel(value: Optional[str]) -> str:
    """
    Normaliza combustible a las claves usadas por las reglas técnicas.

    - VehicleEngine.fuel_type usa "GASOLINA"/"DIESEL"/"HIBRIDO"/"EV".
    - Product.combustible usa "BENCINA"/"DIESEL".
    """
    if not value:
        return ""
    v = value.strip().upper()
    if v in ("BENCINA", "GASOLINA", "NAFTA"):
        return "BENCINA"
    if v.startswith("DIESEL"):
        return "DIESEL"
    return v


def allowed_diameters(cc: Optional[int], fuel: Optional[str]) -> List[float]:
    """
    Reglas Monte Azul: diámetros permitidos por cilindrada y combustible.

    Esta función es reutilizable desde management commands y reglas de
    recomendación por vehículo.
    """
    if not cc:
        return []

    fuel_norm = _norm_fuel(fuel)

    if fuel_norm == "DIESEL":
        if cc <= 1600:
            return [2.0]
        if 1800 <= cc <= 2200:
            return [2.25]
        if 2400 <= cc <= 3000:
            return [2.5, 3.0]
        if cc > 3000:
            return [2.5, 3.0]
        return [2.25]

    if fuel_norm == "BENCINA":
        if cc <= 1600:
            return [1.75, 2.0]
        if 1800 <= cc <= 2200:
            return [2.0, 2.25]
        if cc >= 2400:
            return [2.5]
        return [2.0, 2.25]

    # Sin combustible informado: fallback neutro
    if cc <= 1600:
        return [1.75, 2.0]
    if 1800 <= cc <= 2200:
        return [2.0, 2.25]
    if cc >= 2400:
        return [2.5]
    return [2.0, 2.25]


def year_to_euro(year: Optional[int]) -> Optional[str]:
    """
    Año → norma Euro.

    Mantiene la misma regla que _wizard_year_to_euro del catálogo:
    - <=2005: EURO3
    - 2006–2010: EURO4
    - >=2011: EURO5
    """
    if year is None:
        return None
    try:
        y = int(year)
    except (TypeError, ValueError):
        return None
    if y <= 2005:
        return "EURO3"
    if y <= 2010:
        return "EURO4"
    return "EURO5"


__all__ = ["allowed_diameters", "year_to_euro"]

