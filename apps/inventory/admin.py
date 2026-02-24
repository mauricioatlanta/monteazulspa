from django.contrib import admin
from .models import StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "movement_type", "quantity", "related_order", "reason", "created_by", "created_at")
    list_filter = ("movement_type",)
