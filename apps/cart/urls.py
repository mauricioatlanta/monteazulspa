from django.urls import path
from . import views

app_name = "cart"

urlpatterns = [
    path("", views.cart_view, name="view"),
    path("add/<slug:slug>/", views.cart_add, name="add"),
    path("remove/<slug:slug>/", views.cart_remove, name="remove"),
    path("update/<slug:slug>/", views.cart_update, name="update"),
    path("count/", views.cart_count, name="count"),
]
