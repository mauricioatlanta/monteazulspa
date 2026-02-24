"""
Vistas Webpay Plus: iniciar pago y retorno (commit).
Transbank redirige por POST a return_url; se hace commit del token para confirmar.
"""

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

from .models import Order
from .webpay import webpay_tx
from .views_payments import payment_success


@require_GET
@transaction.atomic
def webpay_start(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if order.status == Order.Status.PAID:
        return render(request, "cart/payment_success.html", {"order": order})

    if order.status not in (Order.Status.DRAFT, Order.Status.PENDING_PAYMENT):
        messages.warning(request, "Esta orden no está disponible para pago.")
        return redirect("cart:view")

    order.status = Order.Status.PENDING_PAYMENT
    order.save(update_fields=["status", "updated_at"])

    buy_order = order.order_number or f"MAZ-{order.id:06d}"
    session_id = str(order.id)
    amount = int(order.total)
    return_url = settings.TBK_RETURN_URL

    tx = webpay_tx()
    resp = tx.create(buy_order, session_id, amount, return_url)

    order.webpay_token = resp["token"]
    order.save(update_fields=["webpay_token", "updated_at"])

    return render(
        request,
        "cart/webpay_redirect.html",
        {
            "webpay_url": resp["url"],
            "token_ws": resp["token"],
            "order": order,
        },
    )


@csrf_exempt
@require_POST
@transaction.atomic
def webpay_return(request):
    token_ws = request.POST.get("token_ws")

    if not token_ws:
        messages.warning(request, "Pago cancelado o expirado.")
        return render(request, "cart/payment_fail.html", {"order": None})

    tx = webpay_tx()
    resp = tx.commit(token_ws)

    response_code = resp.get("response_code")
    status = (resp.get("status") or "").upper()

    order = Order.objects.select_for_update().filter(webpay_token=token_ws).first()
    if not order:
        messages.error(request, "No se encontró la orden asociada a este pago.")
        return render(request, "cart/payment_fail.html", {"order": None})

    order.webpay_status = status
    order.webpay_response_code = response_code
    order.webpay_authorization_code = (resp.get("authorization_code") or "") or ""
    order.webpay_payment_type = (resp.get("payment_type_code") or "") or ""
    card = resp.get("card_detail") or {}
    card_num = card.get("card_number") or ""
    last4 = card_num[-4:] if len(card_num) >= 4 and card_num[-4:].isdigit() else ""
    order.webpay_card_last4 = last4
    order.save(
        update_fields=[
            "webpay_status",
            "webpay_response_code",
            "webpay_authorization_code",
            "webpay_payment_type",
            "webpay_card_last4",
            "updated_at",
        ]
    )

    if order.status == Order.Status.PAID:
        return payment_success(request, order_id=order.id)

    if response_code == 0 and status in ("AUTHORIZED", "APPROVED"):
        return payment_success(request, order_id=order.id)

    messages.error(request, "Transacción rechazada o no autorizada.")
    return render(request, "cart/payment_fail.html", {"order": order})
