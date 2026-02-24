# Generated manually for Centro Estratégico

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ConfiguracionEmpresa",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("warranty_days", models.PositiveIntegerField(default=15, help_text="Aplica a productos que no definan garantía propia.", verbose_name="Días de garantía por defecto")),
                ("warranty_terms", models.TextField(blank=True, default="", verbose_name="Términos de garantía")),
                ("comision_vendedores_pct", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=5, verbose_name="% comisión vendedores")),
                ("margen_minimo_recomendado", models.DecimalField(decimal_places=2, default=Decimal("15"), max_digits=5, verbose_name="Margen mínimo recomendado (%)")),
                ("alertas_margen_bajo", models.BooleanField(default=True, verbose_name="Activar alertas de margen bajo")),
                ("modo_estricto_precios", models.BooleanField(default=False, verbose_name="Modo estricto de precios")),
                ("alerta_stock_critico", models.BooleanField(default=True, verbose_name="Activar alerta de stock crítico")),
                ("dias_max_bodega", models.PositiveIntegerField(blank=True, null=True, verbose_name="Días máximos en bodega (opcional)")),
                ("bloqueo_venta_sin_stock", models.BooleanField(default=False, verbose_name="Bloquear venta sin stock")),
                ("notif_whatsapp", models.BooleanField(default=False, verbose_name="WhatsApp automático")),
                ("notif_email", models.BooleanField(default=True, verbose_name="Email automático")),
                ("aviso_ventas_altas", models.BooleanField(default=False, verbose_name="Aviso de ventas altas")),
                ("aviso_perdidas", models.BooleanField(default=False, verbose_name="Aviso de pérdidas")),
                ("actualizado", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Configuración de la empresa",
                "verbose_name_plural": "Configuración de la empresa",
            },
        ),
    ]
