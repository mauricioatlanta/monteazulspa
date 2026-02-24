"""
Normalización de SKU para matching y sku_canonico.

- Usado para: matching zip ↔ DB, media paths, reportes, SEO.
- No cambia el SKU visible; sku_canonico se usa solo internamente.
"""
import re


def normalize_sku_canonical(raw: str) -> str:
    """
    Normaliza un SKU a forma canónica para comparación y almacenamiento.

    - Mayúsculas, guiones bajos → guión, colapsar doble guión, coma → punto, sin espacios.
    - TWCAT con ceros a la izquierda: TWCAT00042 → TWCAT42.
    - CLF con O por 0: CLFOO2 → CLF002 (errores típicos de captura).

    Ejemplos:
        TWCAT0002--200  → TWCAT2-200
        TWCAT052-10,7   → TWCAT52-10.7
        TWCAT042_200    → TWCAT42-200
        CLFOO2-225      → CLF002-225
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = str(raw).strip().upper().replace(" ", "")
    s = s.replace("_", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    s = s.replace(",", ".")
    # TWCAT + ceros a la izquierda del número
    m = re.match(r"^(TWCAT)0+([0-9]+)(.*)$", s)
    if m:
        s = f"{m.group(1)}{int(m.group(2))}{m.group(3)}"
    # CLF + O como 0 en el bloque alfanumérico (CLFOO2 → CLF002)
    m = re.match(r"^(CLF)([O0]+)(\d*)(.*)$", s)
    if m:
        s = f"{m.group(1)}{m.group(2).replace('O', '0')}{m.group(3)}{m.group(4)}"
    return s


def sku_family_prefix(sku_canonical: str) -> str:
    """
    Prefijo "familia" para matching: TWCAT42-200 → TWCAT42, TWCAT237-SENSOR → TWCAT237.
    Usado para mapear zip TWCAT042_250 → producto TWCAT042 (familia TWCAT42).
    """
    if not sku_canonical:
        return ""
    # Quitar sufijos numéricos con guión (-200, -250, -10.7) o -SENSOR, -DIESEL, etc.
    s = sku_canonical
    # TWCAT42-200 → TWCAT42; TWCAT52-10.7 → TWCAT52
    s = re.sub(r"-\d+(\.\d+)?$", "", s)
    # TWCAT237-SENSOR → TWCAT237
    s = re.sub(r"-(SUPER|SENSOR|DIESEL)$", "", s, flags=re.I)
    return s
