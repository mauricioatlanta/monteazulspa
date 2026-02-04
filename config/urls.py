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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),

    # Alias sin namespace para compatibilidad
    path("validar-vehiculo/", core_views.validate_vehicle, name="validate_vehicle"),

    # Sitio público / home con namespace core
    path("", include(("apps.core.urls", "core"), namespace="core")),

    # Catálogo y carrito
    path("productos/", include(("apps.catalog.urls", "catalog"), namespace="catalog")),
    path("carrito/", include(("apps.cart.urls", "cart"), namespace="cart")),
]

# Servir archivos media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
