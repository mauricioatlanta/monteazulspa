"""
Sincroniza ProductImage desde media/products/<SKU>/main.* hacia la BD.

Solo considera carpetas que sean SKUs reales (excluye flexibles, silenciadores, etc.).
Busca main.webp, main.png, main.jpg, main.jpeg en ese orden.
Crea ProductImage si el producto no tiene ya una imagen con esa ruta.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductImage

# Carpetas que NO son SKUs de producto (no crear ProductImage desde ellas)
IGNORE_DIRS = {
    "flexibles",
    "silenciadores",
    "cataliticos",
    "resonantes",
    "colas_de_escape",
}

MAIN_CANDIDATES = ("main.webp", "main.png", "main.jpg", "main.jpeg")


class Command(BaseCommand):
    help = "Sincroniza ProductImage desde media/products/<SKU>/main.* (solo SKUs reales)."

    def handle(self, *args, **options):
        media_root = Path(settings.MEDIA_ROOT)
        products_dir = media_root / "products"
        if not products_dir.is_dir():
            self.stdout.write(self.style.WARNING("No existe media/products/"))
            return

        stats = {"created": 0, "already_existed": 0, "no_product": 0, "no_main": 0}

        for sku_dir in sorted(products_dir.iterdir()):
            if not sku_dir.is_dir():
                continue
            dir_name = sku_dir.name
            if dir_name.lower() in IGNORE_DIRS:
                continue

            # Buscar main.* en orden de preferencia
            main_path = None
            main_rel = None
            for name in MAIN_CANDIDATES:
                p = sku_dir / name
                if p.is_file():
                    main_path = p
                    main_rel = f"products/{dir_name}/{name}"
                    break

            if not main_path or not main_rel:
                stats["no_main"] += 1
                self.stdout.write(f"  [sin main.*] {dir_name}")
                continue

            try:
                product = Product.objects.get(sku=dir_name)
            except Product.DoesNotExist:
                stats["no_product"] += 1
                self.stdout.write(f"  [sin producto] {dir_name}")
                continue

            # ¿Ya existe una ProductImage con esta ruta para este producto?
            if ProductImage.objects.filter(product=product, image=main_rel).exists():
                stats["already_existed"] += 1
                self.stdout.write(f"  [ya existía] {dir_name} -> {main_rel}")
                continue

            # ¿El producto ya tiene imágenes? Crear solo si no tiene ninguna (repoblar los 74 sin imagen)
            if product.images.exists():
                stats["already_existed"] += 1
                self.stdout.write(f"  [ya tiene imágenes] {dir_name}")
                continue

            # Crear ProductImage como principal (posición 1, is_primary=True)
            ProductImage.objects.create(
                product=product,
                image=main_rel,
                alt_text=product.name or "",
                is_primary=True,
                position=1,
            )
            stats["created"] += 1
            self.stdout.write(self.style.SUCCESS(f"  [creada] {dir_name} -> {main_rel}"))

        self.stdout.write("")
        self.stdout.write("Resumen:")
        self.stdout.write(f"  Creadas: {stats['created']}")
        self.stdout.write(f"  Ya existían: {stats['already_existed']}")
        self.stdout.write(f"  Sin producto en BD: {stats['no_product']}")
        self.stdout.write(f"  Sin main.*: {stats['no_main']}")
