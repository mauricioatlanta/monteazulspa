"""
Template tags para SEO: canonical URL, etc.
"""
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag(takes_context=True)
def canonical_url(context, strip_query=True):
    """
    Devuelve la URL canónica absoluta:
    - Host canónico (sin www si CANONICAL_HOST = monteazulspa.cl)
    - Sin querystrings por defecto (?page=, etc.) salvo casos necesarios
    """
    request = context.get("request")
    if not request:
        site_url = getattr(settings, "SITE_URL", "https://monteazulspa.cl").rstrip("/")
        canonical_host = getattr(settings, "CANONICAL_HOST", "monteazulspa.cl").strip()
        return f"https://{canonical_host}/"

    url = request.build_absolute_uri(request.path)
    if strip_query and request.META.get("QUERY_STRING"):
        # Quitar query string (evita ?page=2, utm_*, etc. en canonical)
        url = url.split("?")[0]

    # Normalizar a host canónico (sin www)
    canonical_host = getattr(settings, "CANONICAL_HOST", "monteazulspa.cl").strip()
    site_url = getattr(settings, "SITE_URL", f"https://{canonical_host}").rstrip("/")
    host = request.get_host()
    if host and host.lower().startswith("www.") and not canonical_host.lower().startswith("www."):
        # Reemplazar www. por host canónico
        base = f"https://{canonical_host}"
        path = request.path
        url = f"{base}{path}"
        if not strip_query and request.META.get("QUERY_STRING"):
            url += "?" + request.META["QUERY_STRING"]

    return url
