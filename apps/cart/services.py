"""
Servicios del carrito: envío de emails, etc.
"""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string


def send_order_confirmation_email(order):
    """
    Envía email de confirmación cuando la orden pasa a PAID.
    """
    subject = f"Confirmación de pedido {order.order_number} | MonteAzul SPA"

    message = render_to_string(
        "cart/email/order_confirmation.txt",
        {"order": order},
    )

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [order.email],
        fail_silently=False,
    )
