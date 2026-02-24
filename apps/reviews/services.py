"""
Servicios para reseñas: validar compra verificada.
"""
from django.db.models import Exists, OuterRef

from apps.cart.models import Order, OrderItem


def user_purchased_product(user, product):
    """
    Verifica si el usuario compró el producto (email del pedido coincide con user.email).
    Order con status=PAID y OrderItem con product_id.
    """
    if not user or not user.is_authenticated or not product:
        return False
    return OrderItem.objects.filter(
        order__status=Order.Status.PAID,
        order__email__iexact=user.email,
        product_id=product.id,
    ).exists()


def user_can_review(user, product):
    """Usuario autenticado que compró el producto puede opinar."""
    return user and user.is_authenticated and user_purchased_product(user, product)
