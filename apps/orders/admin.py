from django.contrib import admin
from .models import Order, OrderItem, WarrantyClaim


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = (
        "unit_price_applied", "discount_percent_applied", "discount_amount_applied",
        "cost_price_snapshot", "warranty_days_applied", "warranty_terms_snapshot", "warranty_expiration_date",
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "status", "total", "created_at")
    list_filter = ("status",)
    inlines = [OrderItemInline]
    readonly_fields = ("subtotal", "discount_total", "tax_total", "total", "created_at", "updated_at", "cancelled_at", "cancel_reason")


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "quantity", "unit_price_applied", "warranty_expiration_date")
    list_filter = ("order__status",)


@admin.register(WarrantyClaim)
class WarrantyClaimAdmin(admin.ModelAdmin):
    list_display = ("id", "order_item", "customer", "status", "resolution", "created_at")
    list_filter = ("status", "resolution")
