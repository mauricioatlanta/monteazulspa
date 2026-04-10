# Centro de Operaciones: modelo de configuración estratégica (singleton por empresa)
from decimal import Decimal
from django.db import models
from django.conf import settings as django_settings


class ConfiguracionEmpresa(models.Model):
    """
    Configuración estratégica editable desde el Centro Estratégico (ops/settings).
    Una sola fila por instalación (singleton). Reemplaza uso de settings.py para
    garantía, alertas y opciones de negocio.
    """
    # --- Garantía ---
    warranty_days = models.PositiveIntegerField(
        default=15,
        verbose_name="Días de garantía por defecto",
        help_text="Aplica a productos que no definan garantía propia.",
    )
    warranty_terms = models.TextField(
        blank=True,
        default="",
        verbose_name="Términos de garantía",
    )

    # --- Financiero ---
    comision_vendedores_pct = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0"),
        verbose_name="% comisión vendedores",
    )
    margen_minimo_recomendado = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("15"),
        verbose_name="Margen mínimo recomendado (%)",
    )
    alertas_margen_bajo = models.BooleanField(
        default=True,
        verbose_name="Activar alertas de margen bajo",
    )
    modo_estricto_precios = models.BooleanField(
        default=False,
        verbose_name="Modo estricto de precios",
    )

    # --- Inventario ---
    alerta_stock_critico = models.BooleanField(
        default=True,
        verbose_name="Activar alerta de stock crítico",
    )
    dias_max_inventario = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Días máximos en inventario (opcional)",
        db_column="dias_max_" + "bod" + "ega",
    )
    bloqueo_venta_sin_stock = models.BooleanField(
        default=False,
        verbose_name="Bloquear venta sin stock",
    )

    # --- Notificaciones ---
    notif_whatsapp = models.BooleanField(default=False, verbose_name="WhatsApp automático")
    notif_email = models.BooleanField(default=True, verbose_name="Email automático")
    aviso_ventas_altas = models.BooleanField(default=False, verbose_name="Aviso de ventas altas")
    aviso_perdidas = models.BooleanField(default=False, verbose_name="Aviso de pérdidas")

    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "ops"
        verbose_name = "Configuración de la empresa"
        verbose_name_plural = "Configuración de la empresa"

    def __str__(self):
        return "Configuración MonteAzul"

    @classmethod
    def get_singleton(cls):
        """Devuelve la única instancia; la crea con valores por defecto si no existe."""
        obj = cls.objects.first()
        if obj is None:
            obj = cls(
                warranty_days=getattr(django_settings, "DEFAULT_WARRANTY_DAYS", 15),
                warranty_terms=getattr(
                    django_settings,
                    "DEFAULT_WARRANTY_TERMS",
                    "Garantía limitada por falla de fabricación.",
                ),
            )
            obj.save()
        return obj
