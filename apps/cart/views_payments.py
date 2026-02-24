from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.db import transaction

from apps.catalog.models import Product

from .models import Order
from .services import send_order_confirmation_email


def _clear_cart_session(request):
    request.session["cart"] = {}
    request.session.modified = True


@transaction.atomic
def payment_start(request, order_id):
    """
    Simula el inicio de pago:
    - Pasa la orden de DRAFT -> PENDING_PAYMENT
    - (Más adelante aquí iniciaremos Webpay real)
    """
    order = get_object_or_404(Order, id=order_id)

    if order.status == Order.Status.PAID:
        messages.info(request, "Esta orden ya está pagada.")
        return redirect("cart:payment_success", order_id=order.id)

    if order.status not in (Order.Status.DRAFT, Order.Status.PENDING_PAYMENT):
        messages.warning(request, "Esta orden no está disponible para pago.")
        return redirect("cart:view")

    # Pasa a pendiente de pago
    order.status = Order.Status.PENDING_PAYMENT
    order.save(update_fields=["status", "updated_at"])

    # Por ahora redirigimos a una pantalla de simulación (éxito/fallo)
    return render(request, "cart/payment_simulator.html", {"order": order})


@transaction.atomic
def payment_success(request, order_id):
    """
    Simula pago exitoso:
    - Valida stock actual
    - Descuenta stock
    - Cambia estado a PAID
    - Limpia carrito (Opción A)
    """
    order = get_object_or_404(Order, id=order_id)

    if order.status == Order.Status.PAID:
        _clear_cart_session(request)
        return render(request, "cart/payment_success.html", {"order": order})

    if order.status != Order.Status.PENDING_PAYMENT:
        messages.warning(request, "La orden no está en estado de pago pendiente.")
        return redirect("cart:checkout_review", order_id=order.id)

    # Validar y descontar stock (con bloqueo)
    for it in order.items.select_for_update().all():
        product = Product.objects.select_for_update().filter(id=it.product_id, deleted_at__isnull=True).first()
        if not product or not product.is_active:
            messages.error(request, "Un producto del pedido ya no está disponible.")
            return redirect("cart:payment_fail", order_id=order.id)

        if product.stock < it.quantity:
            messages.error(request, f"Stock insuficiente para {it.name}. Disponible: {product.stock}")
            return redirect("cart:payment_fail", order_id=order.id)

        product.stock -= it.quantity
        product.save(update_fields=["stock"])

    if order.status != Order.Status.PAID:
        order.status = Order.Status.PAID
        order.save(update_fields=["status", "updated_at"])
        send_order_confirmation_email(order)

    _clear_cart_session(request)

    return render(request, "cart/payment_success.html", {"order": order})


@transaction.atomic
def payment_fail(request, order_id):
    """
    Simula fallo de pago:
    - Mantiene la orden en PENDING_PAYMENT (o vuelve a DRAFT si quieres)
    - No limpia carrito
    """
    order = get_object_or_404(Order, id=order_id)

    # si quisieras "volver atrás":
    # if order.status == Order.Status.PENDING_PAYMENT:
    #     order.status = Order.Status.DRAFT
    #     order.save(update_fields=["status", "updated_at"])

    return render(request, "cart/payment_fail.html", {"order": order})
