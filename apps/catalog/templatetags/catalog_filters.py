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
