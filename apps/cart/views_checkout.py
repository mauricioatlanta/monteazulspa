from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction

from .views import get_cart, _cart_items_and_total
from .models import Order, OrderItem


def checkout(request):
    """Formulario de datos y creación de orden. Redirige a checkout_review."""
    cart = get_cart(request)
    if not cart:
        messages.warning(request, "Tu carrito está vacío.")
        return redirect("cart:view")

    items, total = _cart_items_and_total(request)
    if not items:
        request.session["cart"] = {}
        request.session.modified = True
        messages.warning(request, "No hay productos válidos en el carrito.")
        return redirect("cart:view")

    if request.method == "POST":
        full_name = (request.POST.get("full_name") or "").strip()
        email = (request.POST.get("email") or "").strip()
        phone = (request.POST.get("phone") or "").strip()
        if not full_name or not email or not phone:
            messages.error(request, "Completa nombre, email y teléfono.")
            return render(request, "cart/checkout.html", {"cart_items": items, "total": total})

        # Validar stock de nuevo antes de crear la orden
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
        return redirect("cart:checkout_review", order_id=order.id)

    return render(request, "cart/checkout.html", {"cart_items": items, "total": total})


def checkout_review(request, order_id):
    """Revisión de la orden antes de pagar. Botón 'Pagar' lleva a payment_start."""
    order = get_object_or_404(Order, id=order_id)
    if order.status not in (Order.Status.DRAFT, Order.Status.PENDING_PAYMENT):
        messages.warning(request, "Esta orden no está disponible para pago.")
        return redirect("cart:view")
    return render(request, "cart/checkout_review.html", {"order": order})
