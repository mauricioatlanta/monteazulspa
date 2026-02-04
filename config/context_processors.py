"""
Context processors para templates (variables disponibles en todo el sitio).
"""
from django.conf import settings


def whatsapp(request):
    """Inyecta el número de WhatsApp de contacto en todos los templates."""
    number = getattr(settings, "WHATSAPP_NUMBER", "56900000000")
    # Asegurar formato sin + ni espacios para wa.me
    number = str(number).replace("+", "").replace(" ", "").strip()
    return {"whatsapp_number": number or "56900000000"}
