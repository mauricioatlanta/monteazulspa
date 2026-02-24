from django.conf import settings
from django.db import models


class Review(models.Model):
    """Reseña de producto. Solo usuarios que compraron pueden opinar (validación en vista)."""
    product = models.ForeignKey(
        "catalog.Product",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="product_reviews",
    )
    order = models.ForeignKey(
        "cart.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviews",
        help_text="Orden de compra verificada (opcional)",
    )
    rating = models.PositiveSmallIntegerField(choices=[(i, str(i)) for i in range(1, 6)])
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField()
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"
        unique_together = [["product", "user"]]

    def __str__(self):
        return f"{self.product.sku} - {self.user} ({self.rating}★)"
