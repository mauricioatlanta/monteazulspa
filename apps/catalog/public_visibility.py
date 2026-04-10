from django.db.models import Q

# Categorías/repuestos retirados del frontend público e indexación.
REMOVED_TEXT_TERMS = (
    "empaque",
    "empaques",
    "empaquetadura",
    "empaquetaduras",
)

REMOVED_CATEGORY_SLUGS = ("empaquetaduras-de-motor",)

REMOVED_CATEGORY_REDIRECT_SLUGS = (
    "empaquetaduras-de-motor",
    "empaques-de-motor",
    "empaque-de-motor",
    "empaquetadura-de-motor",
    "empaquetaduras-motor",
    "juntas-de-motor",
    "juntas-motor",
)


def text_contains_removed_terms(text):
    if not text:
        return False
    haystack = str(text).strip().lower()
    return any(term in haystack for term in REMOVED_TEXT_TERMS)


def removed_category_q(prefix=""):
    q = Q(**{f"{prefix}slug__in": REMOVED_CATEGORY_REDIRECT_SLUGS})
    for term in REMOVED_TEXT_TERMS:
        q |= Q(**{f"{prefix}name__icontains": term})
    return q


def removed_product_q(prefix=""):
    q = removed_category_q(f"{prefix}category__")
    for term in REMOVED_TEXT_TERMS:
        q |= Q(**{f"{prefix}name__icontains": term})
        q |= Q(**{f"{prefix}slug__icontains": term})
    return q


def exclude_removed_categories(qs):
    return qs.exclude(removed_category_q())


def exclude_removed_products(qs):
    return qs.exclude(removed_product_q())
