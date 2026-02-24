from decimal import Decimal
from django.db import models
from django.utils import timezone

from apps.catalog.models import Product


class OrderStatus(models.TextChoices):
    PENDING = "PENDING", "Pendiente"
    PAID = "PAID", "Pagado"
    PREPARATION = "PREPARATION", "En preparación"
    SHIPPED = "SHIPPED", "Enviado"
    COMPLETED = "COMPLETED", "Completado"
    CANCELLED = "CANCELLED", "Anulado"


class Order(models.Model):
    """Venta. Totales congelados al momento de la venta."""
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=OrderStatus.choices,
        default=OrderStatus.PENDING,
    )
    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    discount_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    tax_total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    total = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Orden"
        verbose_name_plural = "Órdenes"

    def __str__(self):
        return f"Orden #{self.pk} - {self.customer} - {self.get_status_display()}"


class OrderItem(models.Model):
    """
    Línea de venta. CRÍTICO: nada se recalcula hacia atrás.
    Precio, descuento, costo y garantía quedan congelados.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    unit_price_applied = models.DecimalField(max_digits=12, decimal_places=2)
    discount_percent_applied = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0")
    )
    discount_amount_applied = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0")
    )
    cost_price_snapshot = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0"),
        verbose_name="Costo al momento de la venta",
    )
    # Garantía snapshot
    warranty_days_applied = models.PositiveIntegerField(null=True, blank=True)
    warranty_terms_snapshot = models.TextField(blank=True, default="")
    warranty_expiration_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Línea de orden"
        verbose_name_plural = "Líneas de orden"

    def __str__(self):
        return f"{self.order_id} - {self.product.sku} x {self.quantity}"

    @property
    def line_total(self):
        return (self.unit_price_applied * self.quantity) - self.discount_amount_applied

    def is_warranty_valid(self):
        if not self.warranty_expiration_date:
            return False
        return timezone.now().date() <= self.warranty_expiration_date


class WarrantyClaimStatus(models.TextChoices):
    OPEN = "OPEN", "Abierto"
    APPROVED = "APPROVED", "Aprobado"
    REJECTED = "REJECTED", "Rechazado"


class WarrantyClaimResolution(models.TextChoices):
    REPLACE = "REPLACE", "Cambio"
    REFUND = "REFUND", "Devolución"
    NONE = "NONE", "Sin resolución"


class WarrantyClaim(models.Model):
    """Reclamo de garantía. Flujo: buscar venta → validar vigencia → registrar → resolver."""
    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.PROTECT,
        related_name="warranty_claims",
    )
    customer = models.ForeignKey(
        "customers.CustomerProfile",
        on_delete=models.PROTECT,
        related_name="warranty_claims",
    )
    claim_reason = models.TextField(verbose_name="Motivo del reclamo")
    status = models.CharField(
        max_length=20,
        choices=WarrantyClaimStatus.choices,
        default=WarrantyClaimStatus.OPEN,
    )
    resolution = models.CharField(
        max_length=20,
        choices=WarrantyClaimResolution.choices,
        blank=True,
        default="",
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reclamo de garantía"
        verbose_name_plural = "Reclamos de garantía"

    def __str__(self):
        return f"Reclamo #{self.pk} - {self.order_item} - {self.get_status_display()}"
