from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import Order, OrderItem
from .views import _cart_items_and_total, get_cart


def checkout(request):
    """Formulario de datos y creacion de orden."""
    cart = get_cart(request)
    if not cart:
        messages.warning(request, "Tu carrito esta vacio.")
        return redirect("cart:view")

    items, total = _cart_items_and_total(request)
    if not items:
        request.session["cart"] = {}
        request.session.modified = True
        messages.warning(request, "No hay productos validos en el carrito.")
        return redirect("cart:view")

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        if not full_name or not email or not phone:
            messages.error(request, "Completa nombre, email y telefono.")
            return render(request, "cart/checkout.html", {"cart_items": items, "total": total})

        for item in items:
            if item["quantity"] > item["product"].stock:
                messages.error(
                    request,
                    f"Stock insuficiente para {item['product'].name}. Disponible: {item['product'].stock}",
                )
                return render(request, "cart/checkout.html", {"cart_items": items, "total": total})

        with transaction.atomic():
            order = Order.objects.create(
                status=Order.Status.DRAFT,
                full_name=full_name,
                email=email,
                phone=phone,
                delivery_method="DELIVERY",
                subtotal=total,
                shipping_cost=0,
                total=total,
            )
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product_id=item["product"].id,
                    slug=item["product"].slug,
                    name=item["product"].name,
                    unit_price=item["unit_price"],
                    quantity=item["quantity"],
                )
        return redirect("cart:checkout_transfer", order_id=order.id)

    return render(request, "cart/checkout.html", {"cart_items": items, "total": total})


def checkout_review(request, order_id):
    """
    Alias temporal mientras Webpay esta deshabilitado.
    Mantiene compatibilidad con links existentes y deriva al flujo de transferencia.
    """
    return redirect("cart:checkout_transfer", order_id=order_id)


@transaction.atomic
def checkout_transfer(request, order_id):
    """Pantalla temporal de instrucciones de transferencia bancaria."""
    order = get_object_or_404(Order, id=order_id)

    if order.status == Order.Status.PAID:
        return render(request, "cart/payment_success.html", {"order": order})

    if order.status not in (Order.Status.DRAFT, Order.Status.PENDING_PAYMENT):
        messages.warning(request, "Esta orden no esta disponible para pago.")
        return redirect("cart:view")

    if order.status == Order.Status.DRAFT:
        order.status = Order.Status.PENDING_PAYMENT
        order.save(update_fields=["status", "updated_at"])

    return render(request, "cart/checkout_transfer.html", {"order": order})
