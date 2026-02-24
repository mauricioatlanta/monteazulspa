from django.urls import path
from . import views
from .views_checkout import checkout, checkout_review
from .views_payments import payment_start, payment_success, payment_fail
from .views_webpay import webpay_start, webpay_return

app_name = "cart"

urlpatterns = [
    # Carrito
    path("", views.cart_view, name="view"),
    path("add/<slug:slug>/", views.cart_add, name="add"),
    path("remove/<slug:slug>/", views.cart_remove, name="remove"),
    path("update/<slug:slug>/", views.cart_update, name="update"),
    path("count/", views.cart_count, name="count"),

    # Checkout
    path("checkout/", checkout, name="checkout"),
    path("checkout/revisar/<int:order_id>/", checkout_review, name="checkout_review"),

    # Flujo de pago interno (simulación)
    path("pago/iniciar/<int:order_id>/", payment_start, name="payment_start"),
    path("pago/exito/<int:order_id>/", payment_success, name="payment_success"),
    path("pago/fallo/<int:order_id>/", payment_fail, name="payment_fail"),

    # Webpay Plus (Transbank)
    path("webpay/iniciar/<int:order_id>/", webpay_start, name="webpay_start"),
    path("webpay/retorno/", webpay_return, name="webpay_return"),
]
