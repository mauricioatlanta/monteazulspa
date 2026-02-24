from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product_id", "slug", "name", "unit_price", "quantity", "line_total")
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "status", "full_name", "email", "phone", "total", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("order_number", "full_name", "email", "phone")
    ordering = ("-created_at",)

    readonly_fields = ("order_number", "created_at", "updated_at", "subtotal", "shipping_cost", "total")
    inlines = [OrderItemInline]

    fieldsets = (
        ("Estado", {"fields": ("status",)}),
        ("Comprador", {"fields": ("full_name", "email", "phone")}),
        ("Entrega", {"fields": ("delivery_method", "region", "comuna", "address_line1", "address_reference")}),
        ("Totales", {"fields": ("subtotal", "shipping_cost", "total")}),
        ("Observaciones", {"fields": ("notes",)}),
        ("Sistema", {"fields": ("order_number", "created_at", "updated_at")}),
    )


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("order", "name", "quantity", "unit_price", "line_total")
    search_fields = ("name", "slug")
    list_select_related = ("order",)
    readonly_fields = ("line_total",)
