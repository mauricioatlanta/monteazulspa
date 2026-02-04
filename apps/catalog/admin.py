from django.contrib import admin
from .models import (
    Category, Product, ProductImage,
    VehicleBrand, VehicleModel, VehicleEngine,
    ProductCompatibility,
)

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    max_num = ProductImage.MAX_IMAGES_PER_PRODUCT
    fields = ("position", "image", "alt_text", "is_primary")
    ordering = ("position",)

class ProductCompatibilityInline(admin.TabularInline):
    model = ProductCompatibility
    extra = 1

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "sku",
        "name",
        "price",
        "cost_price",
        "weight",
        "volume",
        "stock",
        "quality_score",
        "is_publishable",
        "is_active",
    )
    list_filter = ("is_publishable", "is_active", "category", "euro_norm")
    search_fields = ("sku", "name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductCompatibilityInline]
    fieldsets = (
        (None, {"fields": ("sku", "name", "slug", "category")}),
        (
            "Precios y logística",
            {
                "fields": ("price", "cost_price", "weight", "volume"),
                "description": "Precio de venta, precio de compra, peso (kg) y volumen.",
            },
        ),
        ("Stock", {"fields": ("stock", "stock_minimum_alert")}),
        (
            "Técnicos",
            {"fields": ("euro_norm", "material", "install_type")},
        ),
        (
            "Publicación",
            {"fields": ("is_active", "deleted_at", "quality_score", "is_publishable")},
        ),
    )

    actions = ["recalculate_quality"]

    def recalculate_quality(self, request, queryset):
        for p in queryset:
            p.refresh_quality(save=True)

admin.site.register(Category)
admin.site.register(VehicleBrand)
admin.site.register(VehicleModel)
admin.site.register(VehicleEngine)
