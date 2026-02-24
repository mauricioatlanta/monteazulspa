from django.conf import settings
from django.db import models

from apps.catalog.models import Product


class MovementType(models.TextChoices):
    IN = "IN", "Entrada"
    OUT = "OUT", "Salida"
    ADJUSTMENT = "ADJUSTMENT", "Ajuste"
    RETURN = "RETURN", "Devolución"
    WARRANTY_RETURN = "WARRANTY_RETURN", "Devolución por garantía"


class StockMovement(models.Model):
    """
    Todo cambio de stock debe hacerse vía StockMovement.
    No se permite stock negativo (excepto OWNER).
    """
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="stock_movements",
    )
    movement_type = models.CharField(
        max_length=20,
        choices=MovementType.choices,
    )
    quantity = models.IntegerField(
        help_text="Positivo para IN/RETURN, negativo para OUT.",
    )
    related_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements",
    )
    reason = models.CharField(max_length=255, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_movements_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Movimiento de stock"
        verbose_name_plural = "Movimientos de stock"

    def __str__(self):
        return f"{self.product.sku} {self.get_movement_type_display()} {self.quantity}"
