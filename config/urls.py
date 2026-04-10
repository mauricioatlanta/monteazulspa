"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from django.views.static import serve

from apps.core import views as core_views
from apps.catalog.views import normativas as catalog_normativas
from config.sitemaps import (
    StaticViewSitemap,
    ProductSitemap,
    CategorySitemap,
    BlogPostSitemap,
    VehicleLandingSitemap,
)

sitemaps = {
    "static": StaticViewSitemap,
    "categories": CategorySitemap,
    "products": ProductSitemap,
    "blog": BlogPostSitemap,
    "vehicles": VehicleLandingSitemap,
}

urlpatterns = [
    path("admin/", admin.site.urls),

    # Alias sin namespace para compatibilidad
    path("validar-vehiculo/", core_views.validate_vehicle, name="validate_vehicle"),

    # Home público (nombre 'home' para enlaces desde app cataliticos)
    path("inicio/", core_views.home, name="home"),

    # Sitio público / home con namespace core
    path("", include(("apps.core.urls", "core"), namespace="core")),

    # Catálogo y carrito
    path("productos/", include(("apps.catalog.urls", "catalog"), namespace="catalog")),
    path("normativas/", catalog_normativas, name="normativas"),
    path("carrito/", include(("apps.cart.urls", "cart"), namespace="cart")),
    path("blog/", include(("apps.blog.urls", "blog"), namespace="blog")),
    # API de tracking (lazy loading para evitar import circular)
    path("api/tracking/", include("apps.tracking.urls")),
    # Centro de Operaciones (OWNER / ADMIN_OPERACIONES)
    path("ops/", include(("apps.ops.urls", "ops"), namespace="ops")),
    # Alias /operaciones/ -> mismo que ops (p. ej. /operaciones/catalogo/)
    path("operaciones/", include(("apps.ops.urls", "ops"), namespace="operations")),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="django_sitemap"),
    path(
        "robots.txt",
        TemplateView.as_view(template_name="seo/robots.txt", content_type="text/plain"),
        name="robots_txt",
    ),
    path("nosotros/", TemplateView.as_view(template_name="pages/nosotros.html"), name="nosotros"),
    path("garantias/", TemplateView.as_view(template_name="pages/garantias.html"), name="garantias"),
    path("devoluciones/", TemplateView.as_view(template_name="pages/devoluciones.html"), name="devoluciones"),
    path("faq/", TemplateView.as_view(template_name="pages/faq.html"), name="faq"),
]

# Incluir app cataliticos si está disponible (proyecto hermano en ../cataliticos)
# Usar string para include() hace que Django cargue las URLs bajo demanda (al resolver),
# evitando importar modelos antes de que las apps estén listas.
import sys
from pathlib import Path
_cataliticos_root = Path(settings.BASE_DIR).parent / "cataliticos"
if _cataliticos_root.exists():
    if str(_cataliticos_root) not in sys.path:
        sys.path.insert(0, str(_cataliticos_root))
    urlpatterns += [
        path("cataliticos/", include("cataliticos.urls", namespace="cataliticos")),
    ]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^imagenes/(?P<path>.*)$",
            serve,
            {"document_root": settings.BASE_DIR / "imagenes"},
        ),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Handlers de error personalizados
handler404 = "apps.core.views.page_404"
handler500 = "apps.core.views.page_500"
