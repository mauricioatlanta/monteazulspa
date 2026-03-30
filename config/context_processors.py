"""
Context processors para templates (variables disponibles en todo el sitio).
"""
from django.conf import settings


def whatsapp(request):
    """Inyecta el número de WhatsApp de contacto en todos los templates."""
    number = getattr(settings, "WHATSAPP_NUMBER", "56979503154")
    # Asegurar formato sin + ni espacios para wa.me (ej: +56 9 7950 3154 → 56979503154)
    number = str(number).replace("+", "").replace(" ", "").strip()
    return {"whatsapp_number": number or "56979503154"}


def seo_settings(request):
    """Inyecta variables para SEO (GA, SITE_URL, etc.) en todos los templates."""
    ga_id = getattr(settings, "GOOGLE_ANALYTICS_ID", "") or ""
    site_url = getattr(settings, "SITE_URL", "https://monteazulspa.cl").rstrip("/")
    return {
        "GOOGLE_ANALYTICS_ID": ga_id,
        "show_google_analytics": bool(ga_id) and not getattr(settings, "DEBUG", False),
        "SITE_URL": site_url,
    }


def company_info(request):
    """Ubicación principal (Macul) y corporativa (Providencia) para templates."""
    return {
        "PRIMARY_LOCATION_NAME": "Bodega y Centro de Venta",
        "PRIMARY_ADDRESS_LINE": "Exequiel Fernández 3663, Of. 6",
        "PRIMARY_CITY": "Macul, Santiago, Chile",
        "PRIMARY_MAPS_QUERY": "Exequiel Fernández 3663 of 6, Macul, Santiago, Chile",
        "CORP_LOCATION_NAME": "Oficina Corporativa",
        "CORP_ADDRESS_LINE": getattr(settings, "CORP_ADDRESS_LINE", "Barros Borgoño 71") or "",
        "CORP_CITY": getattr(settings, "CORP_CITY", "Providencia, Santiago, Chile") or "",
        "WHATSAPP_NUMBER_E164": getattr(settings, "WHATSAPP_NUMBER_E164", None)
        or getattr(settings, "WHATSAPP_NUMBER", "56979503154"),
    }


def header_categories(request):
    """Categorías raíz para la barra de navegación (prioridad: DW/LT/LTM)."""
    try:
        from apps.catalog.models import Category

        exclude_slugs = ["por-clasificar", "flexibles"]
        priority_slugs = [
            "cataliticos",
            "flexibles-reforzados",
            "resonador-deportivo-alto-flujo-ltm",
            "silenciador-alto-flujo-lt",
            "silenciador-linea-dw",
        ]

        base = Category.objects.filter(is_active=True, parent__isnull=True).exclude(slug__in=exclude_slugs)
        priority = list(base.filter(slug__in=priority_slugs))
        priority_sorted = [next((c for c in priority if c.slug == s), None) for s in priority_slugs]
        priority_sorted = [c for c in priority_sorted if c]
        rest = list(base.exclude(slug__in=priority_slugs).order_by("name")[: max(0, 8 - len(priority_sorted))])
        cats = priority_sorted + rest
        return {"header_categories": cats}
    except Exception:
        return {"header_categories": []}


def shipping_location_display(request):
    """Ubicación de envío guardada en session para mostrar en header/modal."""
    loc = request.session.get("shipping_location") or {}
    region = loc.get("region", "")
    comuna = loc.get("comuna", "")
    display = ", ".join(filter(None, [comuna, region])) if (region or comuna) else ""
    return {
        "shipping_location_display": display,
        "shipping_location_region": region,
        "shipping_location_comuna": comuna,
        "shipping_display": display or "Agregar ubicación",
        "shipping_region": region,
        "shipping_comuna": comuna,
    }
