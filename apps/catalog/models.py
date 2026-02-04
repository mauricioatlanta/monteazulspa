import uuid
from django.db import models
from django.utils import timezone


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="children"
    )
    is_active = models.BooleanField(default=True)

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

    class Meta:
        unique_together = ("model", "name")

    def __str__(self):
        return f"{self.model} {self.name}"


class Product(models.Model):
    sku = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)

    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")

    # Comercial
    price = models.DecimalField(max_digits=12, decimal_places=2)
    cost_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0, verbose_name="Precio de compra"
    )

    # Peso y volumen (envío / logística)
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Peso (kg)",
        help_text="Peso en kilogramos",
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
        choices=[("EURO3", "Euro 3"), ("EURO4", "Euro 4"), ("EURO5", "Euro 5")],
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

    # Publicación/Auditoría
    is_active = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    quality_score = models.PositiveIntegerField(default=0)
    is_publishable = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def soft_delete(self):
        self.is_active = False
        self.deleted_at = timezone.now()
        self.save(update_fields=["is_active", "deleted_at"])

    def __str__(self):
        return f"{self.sku} - {self.name}"

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


class ProductImage(models.Model):
    """Hasta 4 imágenes por producto (posición 1-4)."""

    MAX_IMAGES_PER_PRODUCT = 4

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/%d/")
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
    model = models.ForeignKey(VehicleModel, on_delete=models.PROTECT)
    engine = models.ForeignKey(VehicleEngine, on_delete=models.PROTECT, null=True, blank=True)

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
        ]

    def __str__(self):
        eng = f" / {self.engine}" if self.engine_id else ""
        return f"{self.product.sku} -> {self.model} {self.year_from}-{self.year_to}{eng}"
