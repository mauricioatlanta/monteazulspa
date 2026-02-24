"""
Middleware para redirección canónica (www vs no-www) y HTTPS.
Evita errores de sesión/cookies entre monteazulspa.cl y www.monteazulspa.cl
y asegura que el navegador marque el sitio como seguro (HTTPS).
"""
from django.http import HttpResponsePermanentRedirect
from django.conf import settings


def _get_canonical_host():
    """Host canónico (ej. monteazulspa.cl). Vacío = no redirigir."""
    return getattr(settings, "CANONICAL_HOST", "").strip()


def _use_secure_redirects():
    """Si debemos forzar HTTPS y host canónico. Solo cuando SSL está listo (SECURE_SSL_REDIRECT=True)."""
    if getattr(settings, "DEBUG", True):
        return False
    return getattr(settings, "SECURE_SSL_REDIRECT", False)


def _is_secure(request) -> bool:
    """
    Detecta si la petición es HTTPS. Detrás de proxy (Cloudflare/PythonAnywhere),
    request.is_secure() puede ser False aunque el usuario esté en HTTPS;
    usar X-Forwarded-Proto como fallback.
    """
    if request.is_secure():
        return True
    xfproto = request.META.get("HTTP_X_FORWARDED_PROTO", "")
    return xfproto.lower() == "https"


class CanonicalHostAndSecureMiddleware:
    """
    Redirige a la URL canónica (https + host canónico) para:
    - Unificar monteazulspa.cl y www.monteazulspa.cl (evitar diferencias de sesión/cookies).
    - Forzar HTTPS para que el navegador no muestre "no seguro".
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not _use_secure_redirects():
            return self.get_response(request)

        canonical_host = _get_canonical_host()
        if not canonical_host:
            return self.get_response(request)

        host = request.get_host().split(":")[0].lower()
        path = request.get_full_path()
        target = f"https://{canonical_host}{path}"

        # Redirigir si no es HTTPS o si el host no es el canónico (un solo destino)
        if not _is_secure(request) or host != canonical_host:
            return HttpResponsePermanentRedirect(target)

        return self.get_response(request)
