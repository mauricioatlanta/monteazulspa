from __future__ import annotations

from typing import Dict, List


def product_kind_from_data(sku: str, name: str, category_name: str, parent_name: str = "") -> str:
    txt = " ".join([sku or "", name or "", category_name or "", parent_name or ""]).upper()
    if "FLEXIBLE" in txt or "FLEXIBLES" in txt:
        return "FLEXIBLE"
    if "CATALIT" in txt or txt.startswith("CLF") or "TWCAT" in txt or txt.startswith("CAT-"):
        return "CATALITICO"
    if "RESONADOR" in txt or txt.startswith("LTM"):
        return "RESONADOR"
    if "SILENCIADOR" in txt or txt.startswith("DW") or txt.startswith("DWR") or txt.startswith("LT"):
        return "SILENCIADOR"
    if "COLA" in txt or "ESCAPE" in txt or txt.startswith("GW-"):
        return "COLA_ESCAPE"
    return "OTRO_ESCAPE"


def smart_requirements(kind: str) -> List[str]:
    if kind == "CATALITICO":
        return ["diametro", "cilindrada", "combustible", "norma"]
    if kind in ("FLEXIBLE", "RESONADOR", "SILENCIADOR"):
        return ["diametro", "largo"]
    if kind == "COLA_ESCAPE":
        return ["diametro"]
    return ["diametro"]


def evaluate_product_for_smart_search(product) -> Dict[str, object]:
    category_name = getattr(getattr(product, "category", None), "name", "") or ""
    parent = getattr(getattr(product, "category", None), "parent", None)
    parent_name = getattr(parent, "name", "") or ""

    kind = product_kind_from_data(
        getattr(product, "sku", "") or "",
        getattr(product, "name", "") or "",
        category_name,
        parent_name,
    )

    diam_in = getattr(product, "diametro_entrada", None)
    diam_out = getattr(product, "diametro_salida", None)
    largo_mm = getattr(product, "largo_mm", None)
    cc = getattr(product, "recommended_displacement_cc", None)
    combustible = (getattr(product, "combustible", None) or "").strip()
    norma = (getattr(product, "euro_norm", None) or "").strip()

    has_diam = diam_in not in (None, "") or diam_out not in (None, "")
    has_largo = largo_mm not in (None, "")
    has_cc = cc not in (None, "")
    has_comb = bool(combustible)
    has_norma = bool(norma)

    missing = []
    reqs = smart_requirements(kind)

    if "diametro" in reqs and not has_diam:
        missing.append("diametro")
    if "largo" in reqs and not has_largo:
        missing.append("largo_mm")
    if "cilindrada" in reqs and not has_cc:
        missing.append("recommended_displacement_cc")
    if "combustible" in reqs and not has_comb:
        missing.append("combustible")
    if "norma" in reqs and not has_norma:
        missing.append("euro_norm")

    ready = len(missing) == 0

    return {
        "kind": kind,
        "ready": ready,
        "missing_fields": missing,
        "required_fields": reqs,
        "diametro_entrada": diam_in,
        "diametro_salida": diam_out,
        "largo_mm": largo_mm,
        "recommended_displacement_cc": cc,
        "combustible": combustible,
        "euro_norm": norma,
        "category_name": category_name,
        "category_parent_name": parent_name,
    }
