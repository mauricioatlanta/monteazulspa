from django.db import models


class TrackingEvent(models.Model):
    """
    Modelo para almacenar eventos de tracking del frontend.
    Permite analizar comportamiento de usuarios sin depender de Google Analytics.
    """
    EVENT_CHOICES = [
        ('whatsapp_click', 'Click en WhatsApp'),
        ('search', 'Búsqueda'),
        ('product_click', 'Click en producto'),
        ('vehicle_search', 'Búsqueda por vehículo'),
        ('add_to_cart', 'Agregar al carrito'),
        ('other', 'Otro'),
    ]
    
    event = models.CharField(
        max_length=50,
        choices=EVENT_CHOICES,
        db_index=True,
        verbose_name="Tipo de evento"
    )
    payload = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Datos del evento",
        help_text="Información adicional del evento en formato JSON"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name="Fecha y hora"
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name="Dirección IP"
    )
    user_agent = models.CharField(
        max_length=500,
        blank=True,
        default="",
        verbose_name="User Agent"
    )
    
    class Meta:
        app_label = 'tracking'
        ordering = ['-created_at']
        verbose_name = "Evento de tracking"
        verbose_name_plural = "Eventos de tracking"
        indexes = [
            models.Index(fields=['-created_at', 'event']),
        ]
    
    def __str__(self):
        return f"{self.event} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
