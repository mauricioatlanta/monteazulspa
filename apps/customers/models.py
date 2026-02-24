from django.conf import settings
from django.db import models


class CustomerProfile(models.Model):
    class CustomerType(models.TextChoices):
        WEB = "WEB", "Cliente Web"
        INTERNO = "INTERNO", "Cliente Interno"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customer_profile",
        help_text="Solo los clientes internos necesitan usuario para iniciar sesión.",
    )

    customer_type = models.CharField(
        max_length=20,
        choices=CustomerType.choices,
        default=CustomerType.WEB,
    )

    is_internal_active = models.BooleanField(
        default=True,
        help_text="Permite desactivar el acceso interno sin borrar el cliente.",
    )

    # % de descuento preferente por cliente interno
    discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Ej: 10.00 = 10% descuento.",
    )

    # Datos empresa (opcional, pero útil para B2B)
    company_name = models.CharField(max_length=200, blank=True, default="")
    rut = models.CharField(max_length=20, blank=True, default="")
    phone = models.CharField(max_length=50, blank=True, default="")

    # Garantía: modificador por cliente interno (opcional)
    # Ej: -7 reduce 7 días a la garantía estándar, 0 no modifica
    warranty_days_modifier = models.IntegerField(
        default=0,
        help_text="Modifica la garantía estándar. Ej: -7 acorta 7 días. 0 = sin cambio.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        label = self.company_name or (self.user.get_username() if self.user else "Cliente")
        return f"{label} ({self.customer_type})"
