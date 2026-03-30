from django.db.models import Q
from .engine_rules_map import ENGINE_RULES


def apply_engine_filter(qs, engine, fuel):
    if not engine or not engine.displacement_cc:
        return qs.none()

    cc = engine.displacement_cc
    fuel = (fuel or "").upper()

    rules = ENGINE_RULES.get(fuel, [])
    allowed_codes = []

    for r in rules:
        if r["min"] <= cc <= r["max"]:
            allowed_codes.extend(r["codes"])

    if not allowed_codes:
        return qs.none()

    q = Q()
    for code in allowed_codes:
        q |= Q(sku__icontains=code)

    return qs.filter(q)
