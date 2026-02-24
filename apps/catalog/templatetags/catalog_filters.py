"""
Filtros de plantilla para el catálogo.
Formato de precios en pesos chilenos: $1.250.000 (sin decimales, punto como separador de miles).
"""
from django import template

register = template.Library()


def format_pesos_cl(value):
    """Formatea un número como precio en pesos chilenos: $1.250.000 sin decimales."""
    try:
        n = int(round(float(value)))
        return "$" + f"{n:,}".replace(",", ".")
    except (TypeError, ValueError):
        return "$0"


@register.filter(name="pesos_cl")
def pesos_cl(value):
    return format_pesos_cl(value)


@register.filter(name="category_menu_name")
def category_menu_name(name):
    """Nombre para el menú de categorías: 'Cataliticos' → 'Convertidores Cataliticos'."""
    if not name:
        return name
    if name.strip() == "Cataliticos":
        return "Convertidores Cataliticos"
    return name


@register.filter(name="flexible_dimensions")
def flexible_dimensions(sku):
    """
    Para productos flexibles: devuelve texto tipo '2.5" x 6" (diámetro x largo en pulgadas)'.
    Si el SKU no es una medida de flexible, devuelve cadena vacía.
    """
    from apps.catalog.flexibles_nomenclature import get_flexible_dimensions_display
    return get_flexible_dimensions_display(sku) or ""
