from django.db import models
from django.utils import timezone


class Order(models.Model):

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Borrador"
        PENDING_PAYMENT = "PENDING_PAYMENT", "Pendiente de pago"
        PAID = "PAID", "Pagado"
        CANCELLED = "CANCELLED", "Cancelado"

    order_number = models.CharField(max_length=20, unique=True, blank=True, default="")

    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT
    )

    # Datos comprador
    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=30)

    # Entrega
    delivery_method = models.CharField(max_length=20, default="DELIVERY")
    region = models.CharField(max_length=80, blank=True, default="")
    comuna = models.CharField(max_length=80, blank=True, default="")
    address_line1 = models.CharField(max_length=180, blank=True, default="")
    address_reference = models.CharField(max_length=180, blank=True, default="")

    # Totales congelados
    subtotal = models.PositiveIntegerField(default=0)
    shipping_cost = models.PositiveIntegerField(default=0)
    total = models.PositiveIntegerField(default=0)

    notes = models.TextField(blank=True, default="")

    # Webpay (Transbank) trazabilidad
    webpay_token = models.CharField(max_length=200, blank=True, default="")
    webpay_status = models.CharField(max_length=50, blank=True, default="")
    webpay_authorization_code = models.CharField(max_length=50, blank=True, default="")
    webpay_response_code = models.IntegerField(null=True, blank=True)
    webpay_payment_type = models.CharField(max_length=10, blank=True, default="")
    webpay_card_last4 = models.CharField(max_length=4, blank=True, default="")

    def __str__(self):
        return f"Orden {self.order_number or 'MAZ-pendiente'} - {self.full_name} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        related_name="items",
        on_delete=models.CASCADE
    )

    product_id = models.PositiveIntegerField()
    slug = models.CharField(max_length=200, blank=True, default="")
    name = models.CharField(max_length=200)

    unit_price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField(default=1)
    line_total = models.PositiveIntegerField(default=0)

    def save(self, *args, **kwargs):
        self.line_total = int(self.unit_price) * int(self.quantity)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} x{self.quantity}"


from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=Order)
def set_order_number(sender, instance: Order, created, **kwargs):
    """
    Genera MAZ-000123 usando el ID real.
    Se ejecuta SOLO si aún no tiene order_number.
    """
    if instance.order_number:
        return

    # Formato: MAZ-000123
    code = f"MAZ-{instance.id:06d}"

    # Update directo para evitar re-disparar lógica rara
    sender.objects.filter(id=instance.id, order_number="").update(order_number=code)
