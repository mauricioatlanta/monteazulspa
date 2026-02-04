from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.home_public, name="home_public"),
    path("home/", views.home, name="home"),
    path("resultados/", views.vehicle_results, name="vehicle_results"),

    # APIs para el validador (JSON)
    path("api/modelos/", views.api_modelos, name="api_modelos"),
    path("api/motores/", views.api_motores, name="api_motores"),
]
