from django.urls import path
from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.product_list, name="product_list"),
    path("api/search/", views.product_search_api, name="product_search_api"),
    path("<slug:slug>/", views.product_detail, name="product_detail"),
]
