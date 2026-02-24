from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('buscar-por-vehiculo/', views.vehicle_search, name='vehicle_search'),
    path('validar-vehiculo/', views.validate_vehicle, name='validate_vehicle'),
    path('api/modelos/', views.api_vehicle_models, name='api_models'),
    path('api/motores/', views.api_vehicle_engines, name='api_engines'),
    path('api/regiones/', views.api_regiones, name='api_regiones'),
    path('api/comunas/', views.api_comunas, name='api_comunas'),
    path('api/set-location/', views.set_location, name='set_location'),
    path('api/shipping-estimate/', views.shipping_estimate, name='shipping_estimate'),
]
