from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('buscar-por-vehiculo/', views.vehicle_search, name='vehicle_search'),
    path('validar-vehiculo/', views.validate_vehicle, name='validate_vehicle'),
    path('api/modelos/', views.api_vehicle_models, name='api_models'),
    path('api/motores/', views.api_vehicle_engines, name='api_engines'),
]
