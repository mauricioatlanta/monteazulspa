from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Trazabilidad: cambios de precio, stock, descuentos, garantías."""
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=80)
    model = models.CharField(max_length=80, blank=True, default="")
    object_id = models.CharField(max_length=100, blank=True, default="")
    description = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Registro de auditoría"
        verbose_name_plural = "Registros de auditoría"

    def __str__(self):
        return f"{self.timestamp} - {self.action} - {self.description[:50]}"
