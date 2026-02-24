from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import (
    Category, Product, ProductImage,
    VehicleBrand, VehicleModel, VehicleEngine,
    ProductCompatibility,
    ProductViewStat,
)


class ProductInline(admin.TabularInline):
    """Permite agregar/editar productos desde la ficha de una categoría."""
    model = Product
    extra = 1
    show_change_link = True
    fields = ("sku", "name", "price", "stock", "is_active", "is_publishable")
    ordering = ("sku",)
    verbose_name = "Producto"
    verbose_name_plural = "Productos de esta categoría"


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
    list_filter = ("is_publishable", "is_active", "category", "euro_norm", "combustible", "tiene_sensor")
    search_fields = ("sku", "name")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline, ProductCompatibilityInline]
    fieldsets = (
        (None, {"fields": ("sku", "name", "slug", "category")}),
        (
            "Precios y logística",
            {
                "fields": ("price", "cost_price", "weight", "length", "width", "height", "volume"),
                "description": "Precio de venta, precio de compra, peso (kg) y dimensiones.",
            },
        ),
        ("Stock", {"fields": ("stock", "stock_minimum_alert")}),
        (
            "Técnicos",
            {
                "fields": (
                    "euro_norm",
                    "combustible",
                    "material",
                    "install_type",
                    "diametro_entrada",
                    "diametro_salida",
                    "largo_mm",
                    "tiene_sensor",
                    "celdas",
                ),
            },
        ),
        (
            "Ficha técnica",
            {
                "fields": ("ficha_tecnica",),
                "description": "Texto con certificaciones y especificaciones. Si está vacío, en la ficha del producto se muestran solo los campos estándar (peso, largo, norma Euro, etc.).",
            },
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

    def get_changeform_initial_data(self, request):
        """Preselecciona la categoría si se llega desde 'Agregar producto' de una categoría."""
        initial = super().get_changeform_initial_data(request)
        cat_id = request.GET.get("category")
        if cat_id:
            initial["category"] = cat_id
        return initial


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "parent", "is_active", "add_product_link")
    list_filter = ("is_active", "parent")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductInline]
    change_form_template = "admin/catalog/category/change_form.html"

    @admin.display(description="Agregar producto")
    def add_product_link(self, obj):
        url = reverse("admin:catalog_product_add") + f"?category={obj.pk}"
        return format_html('<a href="{}">Agregar producto</a>', url)


@admin.register(ProductViewStat)
class ProductViewStatAdmin(admin.ModelAdmin):
    list_display = ("product", "views", "last_viewed")
    list_filter = ()
    search_fields = ("product__sku", "product__name")
    readonly_fields = ("product", "views", "last_viewed")
    ordering = ("-views",)

    def has_add_permission(self, request):
        return False  # Se crean automáticamente al ver un producto


admin.site.register(VehicleBrand)
admin.site.register(VehicleModel)
admin.site.register(VehicleEngine)
