import uuid
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from django.urls import reverse

from .utils.media_paths import product_image_upload_to
from .utils.sku_normalize import normalize_sku_canonical


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_active = models.BooleanField(default=True)
    default_warranty_days = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Días de garantía por defecto",
        help_text="Si está vacío, se usa la garantía global.",
    )
    default_warranty_terms = models.TextField(
        blank=True, default="",
        verbose_name="Términos de garantía por defecto",
    )

    class Meta:
        verbose_name_plural = "Categorías"

    def __str__(self):
        return self.name


class VehicleBrand(models.Model):
    name = models.CharField(max_length=80, unique=True)

    def __str__(self):
        return self.name


class VehicleModel(models.Model):
    brand = models.ForeignKey(VehicleBrand, on_delete=models.PROTECT, related_name="models")
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ("brand", "name")

    def __str__(self):
        return f"{self.brand} {self.name}"


class VehicleEngine(models.Model):
    model = models.ForeignKey(VehicleModel, on_delete=models.PROTECT, related_name="engines")
    name = models.CharField(max_length=120)
    fuel_type = models.CharField(
        max_length=20,
        choices=[("GASOLINA", "Gasolina"), ("DIESEL", "Diésel"), ("HIBRIDO", "Híbrido"), ("EV", "EV")],
        null=True,
        blank=True,
    )
    displacement_cc = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Cilindrada del motor en centímetros cúbicos (cc).",
    )

    class Meta:
        unique_together = ("model", "name")

    def __str__(self):
        return f"{self.model} {self.name}"


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    sku_canonico = models.CharField(
        max_length=60,
        blank=True,
        null=True,
        db_index=True,
        verbose_name="SKU canónico",
        help_text="SKU normalizado para matching con zip, imágenes y reportes. No cambiar el SKU visible.",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")

    # Comercial
    price = models.DecimalField(max_digits=12, decimal_places=2)
    compare_at_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Precio anterior / comparar",
        help_text="Precio normal para mostrar tachado y calcular descuento. Si está vacío no se muestra oferta.",
    )
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Precio de compra"
    )

    # Peso y dimensiones (envío / logística)
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Peso (kg)",
        help_text="Peso en kilogramos",
    )
    length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Largo (cm)",
        help_text="Largo en centímetros",
    )
    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Ancho (cm)",
        help_text="Ancho en centímetros",
    )
    height = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Alto (cm)",
        help_text="Alto en centímetros",
    )
    volume = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Volumen",
        help_text="Volumen en litros o m³ según convención",
    )

    stock = models.PositiveIntegerField(default=0)
    stock_minimum_alert = models.PositiveIntegerField(default=3)

    # Técnicos (clave para escapes/catalíticos)
    euro_norm = models.CharField(
        max_length=10,
        choices=[
            ("EURO2", "Euro 2"),
            ("EURO3", "Euro 3"),
            ("EURO4", "Euro 4"),
            ("EURO5", "Euro 5"),
        ],
        null=True,
        blank=True,
    )
    material = models.CharField(
        max_length=30,
        choices=[("ACERO", "Acero"), ("INOX", "Acero inoxidable"), ("CERAMICO", "Cerámico")],
        null=True,
        blank=True,
    )
    install_type = models.CharField(
        max_length=30,
        choices=[("PLUG_PLAY", "Plug & Play"), ("SOLDADURA", "Requiere soldadura")],
        null=True,
        blank=True,
    )
    # Especificaciones técnicas para catalíticos (filtros y ficha industrial)
    combustible = models.CharField(
        max_length=20,
        choices=[("BENCINA", "Bencina"), ("DIESEL", "Diesel")],
        null=True,
        blank=True,
        verbose_name="Combustible",
    )
    diametro_entrada = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Diámetro entrada (pulg.)",
        help_text="Diámetro de entrada en pulgadas (ej. 2.5)",
    )
    diametro_salida = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name="Diámetro salida (pulg.)",
    )
    largo_mm = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Largo (mm)",
        help_text="Largo total en milímetros",
    )
    tiene_sensor = models.BooleanField(
        default=False,
        verbose_name="Con sensor O2",
    )
    celdas = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Celdas (CPSI)",
        help_text="Densidad de celdas (ej. 200 CPSI)",
    )
    recommended_cc_min = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Cilindrada mínima recomendada (cc)",
        help_text="Rango de cilindrada para catalíticos: el vehículo debe tener cc >= este valor.",
    )
    recommended_cc_max = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        verbose_name="Cilindrada máxima recomendada (cc)",
        help_text="Rango de cilindrada para catalíticos: el vehículo debe tener cc <= este valor.",
    )

    # Ficha técnica / descripción (texto largo para certificaciones, especificaciones detalladas)
    ficha_tecnica = models.TextField(
        blank=True,
        default="",
        verbose_name="Ficha técnica / Descripción",
        help_text="Texto con ficha técnica, certificaciones y especificaciones. Si está vacío, se muestran solo los campos técnicos estándar.",
    )
    compatibility_notes = models.TextField(
        blank=True,
        default="",
        verbose_name="Notas de compatibilidad (años, generaciones, otros modelos)",
        help_text="Texto opcional que se muestra en la sección Compatibilidad vehicular: años, generación del modelo, otros vehículos que usan el mismo convertidor, etc.",
    )

    # Garantía (jerarquía: producto → categoría → global)
    has_warranty = models.BooleanField(
        default=True,
        verbose_name="Tiene garantía",
    )
    warranty_days = models.PositiveIntegerField(
        null=True, blank=True,
        verbose_name="Días de garantía",
        help_text="Si está vacío, se usa categoría o valor global.",
    )
    warranty_terms = models.TextField(
        blank=True, default="",
        verbose_name="Términos de garantía",
    )

    # Publicación/Auditoría
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    quality_score = models.PositiveIntegerField(default=0)
    is_publishable = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def build_unique_slug(self, source=None):
        base_source = (source or self.slug or self.sku or self.name or "").strip()
        base_slug = slugify(base_source)[:260] or "producto"
        candidate = base_slug
        suffix = 2

        existing = Product.objects.all()
        if self.pk:
            existing = existing.exclude(pk=self.pk)

        while existing.filter(slug=candidate).exists():
            suffix_text = f"-{suffix}"
            candidate = f"{base_slug[:280 - len(suffix_text)]}{suffix_text}"
            suffix += 1

        return candidate

    def _get_ops_admin_url(self, action="detail"):
        if not self.pk:
            return ""

        if self.slug:
            route_name = {
                "detail": "ops:catalog_admin_detail",
                "edit": "ops:catalog_admin_edit",
                "delete": "ops:catalog_admin_delete",
            }[action]
            return reverse(route_name, kwargs={"slug": self.slug})

        fallback_route = {
            "detail": "ops:catalog_admin_detail_by_pk",
            "edit": "ops:catalog_admin_edit_by_pk",
            "delete": "ops:catalog_admin_delete_by_pk",
        }[action]
        return reverse(fallback_route, kwargs={"pk": self.pk})

    def get_ops_admin_detail_url(self):
        return self._get_ops_admin_url("detail")

    def get_ops_admin_edit_url(self):
        return self._get_ops_admin_url("edit")

    def get_ops_admin_delete_url(self):
        return self._get_ops_admin_url("delete")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.build_unique_slug()
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = list(set(kwargs["update_fields"]) | {"slug"})
        # Rellenar sku_canonico para matching/media si está vacío
        if self.sku and not self.sku_canonico:
            self.sku_canonico = normalize_sku_canonical(self.sku) or None
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = list(set(kwargs["update_fields"]) | {"sku_canonico"})
        # Asegurar que la categoría esté cargada
        category_slug = None
        if self.category_id:
            try:
                category_slug = self.category.slug
            except Exception:
                pass

        # Todas las categorías de flexibles son reforzados: flexibles, flexibles-reforzados, flexibles-normales, flexibles-con-extension
        FLEXIBLES_SLUGS = ("flexibles", "flexibles-reforzados", "flexibles-normales", "flexibles-con-extension")
        if category_slug in FLEXIBLES_SLUGS:
            # --- CORREGIR NOMBRE (asegurar "reforzado") ---
            if not self.name or "reforz" not in self.name.lower():
                if self.name and "flexible" in self.name.lower():
                    self.name = self.name.replace("Flexible", "Flexible Reforzado")
                else:
                    self.name = f"Flexible Reforzado {self.sku}"

            # --- CORREGIR FICHA TECNICA ---
            if self.ficha_tecnica:
                if not self.ficha_tecnica.strip().lower().startswith("flexible reforz"):
                    self.ficha_tecnica = f"Flexible reforzado. {self.ficha_tecnica}"

            # Autoincluir name y ficha_tecnica en update_fields para que siempre se guarden
            update_fields = kwargs.get("update_fields", None)
            if update_fields is not None:
                uf = set(update_fields)
                uf.add("name")
                uf.add("ficha_tecnica")
                kwargs["update_fields"] = list(uf)

        super().save(*args, **kwargs)

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    def __str__(self):
        return f"{self.sku} - {self.name}"

    def get_absolute_url(self):
        if not self.slug:
            return ""
        return reverse("catalog:product_detail", kwargs={"slug": self.slug})

    def compute_quality_score(self) -> int:
        score = 0

        # Base mínima
        if self.sku: score += 10
        if self.name: score += 10
        if self.category_id: score += 10
        if self.price and self.price > 0: score += 10

        # Técnicos (muy relevantes en escape)
        if self.euro_norm: score += 10
        if self.material: score += 10
        if self.install_type: score += 10

        # Compatibilidad
        compat_count = self.compatibilities.filter(is_active=True).count()
        if compat_count >= 1: score += 15
        if compat_count >= 5: score += 5

        # Imágenes
        img_count = self.images.count()
        if img_count >= 1: score += 10
        if img_count >= 3: score += 5

        return min(score, 100)

    def refresh_quality(self, save=True):
        score = self.compute_quality_score()
        self.quality_score = score
        self.is_publishable = score >= 70 and self.is_active and not self.deleted_at
        if save:
            self.save(update_fields=["quality_score", "is_publishable"])

    def get_effective_warranty_days(self):
        """Jerarquía: producto → categoría → ConfiguracionEmpresa → settings."""
        if not self.has_warranty:
            return None
        if self.warranty_days is not None:
            return self.warranty_days
        if self.category and self.category.default_warranty_days is not None:
            return self.category.default_warranty_days
        try:
            from apps.ops.models import ConfiguracionEmpresa
            c = ConfiguracionEmpresa.get_singleton()
            if c:
                return c.warranty_days
        except Exception:
            pass
        from django.conf import settings
        return getattr(settings, "DEFAULT_WARRANTY_DAYS", 15)

    def get_effective_warranty_terms(self):
        """Jerarquía: producto → categoría → ConfiguracionEmpresa → settings."""
        if not self.has_warranty:
            return ""
        if self.warranty_terms:
            return self.warranty_terms
        if self.category and self.category.default_warranty_terms:
            return self.category.default_warranty_terms
        try:
            from apps.ops.models import ConfiguracionEmpresa
            c = ConfiguracionEmpresa.get_singleton()
            if c and c.warranty_terms:
                return c.warranty_terms
        except Exception:
            pass
        from django.conf import settings
        return getattr(settings, "DEFAULT_WARRANTY_TERMS", "Garantía limitada por falla de fabricación.")

    def get_precio_neto(self):
        """Precio sin IVA. Si PRICE_INCLUDES_IVA=True, despeja el neto del precio guardado."""
        from django.conf import settings
        iva = getattr(settings, "IVA_PERCENT", 19)
        incluye = getattr(settings, "PRICE_INCLUDES_IVA", True)
        if not self.price:
            return None
        if incluye:
            return round(self.price / (1 + iva / 100), 2)
        return self.price

    def get_precio_con_iva(self):
        """Precio con IVA incluido. Para punto de venta y catálogo público."""
        from django.conf import settings
        iva = getattr(settings, "IVA_PERCENT", 19)
        incluye = getattr(settings, "PRICE_INCLUDES_IVA", True)
        if not self.price:
            return None
        if incluye:
            return self.price
        return round(self.price * (1 + iva / 100), 2)


class ProductImage(models.Model):
    """Hasta 4 imágenes por producto (posición 1-4)."""

    MAX_IMAGES_PER_PRODUCT = 4

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to=product_image_upload_to)
    alt_text = models.CharField(max_length=160, blank=True, default="")
    is_primary = models.BooleanField(default=False)
    position = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Posición (1-4)",
        help_text="Orden de la imagen para este producto (máximo 4 imágenes).",
    )

    class Meta:
        ordering = ["product", "position"]
        constraints = [
           models.CheckConstraint(
               condition=models.Q(position__gte=1) & models.Q(position__lte=4),
               name="productimage_position_1_to_4",
           ),
            models.UniqueConstraint(
                fields=["product", "position"],
                name="unique_product_image_position",
            ),
        ]


class ProductCompatibility(models.Model):
    CONFIDENCE_CHOICES = [
        ("ALTA", "Alta"),
        ("MEDIA", "Media"),
        ("BAJA", "Baja"),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="compatibilities")
    brand = models.ForeignKey(VehicleBrand, on_delete=models.PROTECT)
    model = models.ForeignKey(
        VehicleModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Si es NULL, compatibilidad amplia por marca (todos los modelos).",
    )
    engine = models.ForeignKey(VehicleEngine, on_delete=models.PROTECT, null=True, blank=True)
    displacement_cc = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        help_text="Cilindrada objetivo en centímetros cúbicos (cc). Si está vacío, se usa la del motor.",
    )

    year_from = models.PositiveIntegerField()
    year_to = models.PositiveIntegerField()

    fuel_type = models.CharField(
        max_length=20,
        choices=[("GASOLINA", "Gasolina"), ("DIESEL", "Diésel"), ("HIBRIDO", "Híbrido"), ("EV", "EV")],
        null=True,
        blank=True,
    )

    notes = models.CharField(max_length=255, blank=True, default="")
    confidence = models.CharField(max_length=10, choices=CONFIDENCE_CHOICES, default="ALTA")

    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=["brand", "model", "year_from", "year_to"]),
            models.Index(fields=["product", "is_active"]),
            models.Index(
                fields=["brand", "model", "displacement_cc", "year_from", "year_to"],
                name="cat_pc_brand_model_cc_year_idx",
            ),
        ]

    def __str__(self):
        model_str = str(self.model) if self.model_id else "(todos)"
        eng = f" / {self.engine}" if self.engine_id else ""
        return f"{self.product.sku} -> {model_str} {self.year_from}-{self.year_to}{eng}"


class ProductViewStat(models.Model):
    """Estadísticas de vistas por producto para dashboard SEO interno (sin terceros)."""
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="view_stat",
    )
    views = models.PositiveIntegerField(default=0)
    last_viewed = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-views"]
        verbose_name = "Estadística de vistas"
        verbose_name_plural = "Estadísticas de vistas"

    def __str__(self):
        return f"{self.product.sku}: {self.views} vistas"


class SearchLog(models.Model):
    """
    Log simple de búsquedas para análisis de demanda y brechas de catálogo.
    """

    query = models.CharField(max_length=255)
    cc = models.IntegerField(null=True, blank=True, db_index=True)
    fuel = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    year = models.IntegerField(null=True, blank=True, db_index=True)
    results_count = models.IntegerField()
    is_relaxed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.query} ({self.results_count} resultados)"
