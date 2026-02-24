# apps/ops/middleware.py


class OpsNoCacheMiddleware:
    """
    Evita que /ops/ y /operaciones/ se cacheen (Cloudflare, navegador, CDN).
    Seguridad: no exponer HTML de área administrativa vía caché.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/ops/") or request.path.startswith("/operaciones/"):
            response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response["Pragma"] = "no-cache"
        return response
