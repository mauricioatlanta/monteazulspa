from django.urls import path
from . import views
from .views_escape_search import EscapeSearchView
from .views_vehicle_search import (
    vehicle_search_page,
    vehicle_models_api,
    vehicle_engines_api,
    vehicle_products_api,
)

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("buscar/", views.smart_search_redirect, name="smart_search"),
    path("buscar-sugerencias/", views.smart_search_suggestions_api, name="smart_search_suggestions_api"),
    path(
        "buscador-vehiculo/",
        vehicle_search_page,
        name="vehicle_search",
    ),
    path("api/vehicle-models/", vehicle_models_api, name="vehicle_models_api"),
    path("api/vehicle-engines/", vehicle_engines_api, name="vehicle_engines_api"),
    path("api/vehicle-products/", vehicle_products_api, name="vehicle_products_api"),
    path("busqueda-escape/", EscapeSearchView.as_view(), name="escape_search"),
    path("buscar-escape/", views.buscar_escape, name="buscar_escape"),
    path("escape/<slug:diametro_slug>/", views.escape_seo_redirect, name="escape_seo_diametro"),
    path("escape/<slug:diametro_slug>/<slug:largo_slug>/", views.escape_seo_redirect, name="escape_seo_diametro_largo"),
    path("listado-precios/", views.lista_precios, name="lista_precios"),
    path("asistente-cataliticos/", views.asistente_cataliticos, name="asistente_cataliticos"),
    path("normativas/", views.normativas, name="normativas"),
    path("convertidores-cataliticos-twg/", views.cataliticos_twg_opciones, name="twg_opciones"),
    path("api/search/", views.product_search_api, name="product_search_api"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
    path("<slug:slug>/reseña/", views.review_submit, name="review_submit"),
]
