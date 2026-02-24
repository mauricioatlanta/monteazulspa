from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("asistente-cataliticos/", views.asistente_cataliticos, name="asistente_cataliticos"),
    path("normativas/", views.normativas, name="normativas"),
    path("convertidores-cataliticos-twg/", views.cataliticos_twg_opciones, name="twg_opciones"),
    path("api/search/", views.product_search_api, name="product_search_api"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
    path("<slug:slug>/reseña/", views.review_submit, name="review_submit"),
]
