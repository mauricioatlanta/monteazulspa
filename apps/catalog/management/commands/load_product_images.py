"""
Carga imágenes adicionales por SKU desde una carpeta local.

Estructura esperada:
  imagenes/
    SIL001/
      main.jpg
      interior.jpg
      lateral.jpg
    SIL002/
      main.jpg
      interior.jpg

- Busca producto por SKU (nombre de subcarpeta).
- La primera imagen (main.* si existe, si no la primera alfabética) → is_primary=True, position=1.
- Resto hasta 4 imágenes → is_primary=False, position 2,3,4.
- Guarda en media/products/<SKU>/ (vía ImageField upload_to).

Uso:
  python manage.py load_product_images imagenes
  python manage.py load_product_images imagenes --replace
  python manage.py load_product_images C:\\Users\\...\\ZIP_extracted --dry-run
"""
import os
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductImage

# Extensiones de imagen aceptadas (minúsculas)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Nombres que se consideran "principal" (orden de prioridad)
MAIN_FILENAMES = ("main", "principal", "01", "1")


def _image_order_key(path: Path) -> tuple:
    """Ordenar: main.* primero, luego el resto alfabéticamente."""
    name_lower = path.stem.lower()
    for i, main_name in enumerate(MAIN_FILENAMES):
        if name_lower == main_name or name_lower.startswith(main_name + "."):
            return (0, i, path.name.lower())
    return (1, 0, path.name.lower())


class Command(BaseCommand):
    help = "Carga ProductImage desde carpeta con subcarpetas por SKU (main.jpg, interior.jpg, etc.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "source",
            type=str,
            help="Ruta a la carpeta que contiene subcarpetas por SKU (ej: imagenes/ o ruta del ZIP extraído).",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Reemplazar imágenes existentes del producto (por defecto solo añade si no hay 4).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo listar qué se haría, sin crear ni borrar.",
        )

    def handle(self, *args, **options):
        raw_source = options["source"].strip()
        source = Path(raw_source)
        if not source.is_absolute():
            # Rutas relativas se resuelven desde el proyecto (BASE_DIR)
            base_dir = Path(settings.BASE_DIR)
            source = (base_dir / raw_source).resolve()
        else:
            source = source.resolve()
        replace = options["replace"]
        dry_run = options["dry_run"]

        if not source.is_dir():
            self.stdout.write(self.style.ERROR(f"No existe la carpeta: {source}"))
            self.stdout.write(
                "Crea la carpeta en el proyecto (ej: mkdir imagenes) y coloca dentro "
                "subcarpetas por SKU con las imágenes (ej: imagenes/SIL001/main.jpg), "
                "o indica la ruta absoluta donde ya tienes las imágenes."
            )
            return

        subdirs = [d for d in source.iterdir() if d.is_dir()]
        if not subdirs:
            self.stdout.write(self.style.WARNING(f"La carpeta existe pero está vacía: {source}"))
            self.stdout.write(
                "Añade dentro subcarpetas cuyo nombre sea el SKU del producto "
                "(ej: LT041, DW002). Dentro de cada una, pon las imágenes: main.jpg, interior.jpg, etc."
            )
            self.stdout.write("Ejemplo: imagenes/LT041/main.jpg  imagenes/LT041/interior.jpg")
            return

        stats = {"created": 0, "replaced": 0, "skipped_no_product": 0, "skipped_no_images": 0, "skipped_full": 0}

        for sku_dir in sorted(subdirs):
            if not sku_dir.is_dir():
                continue
            sku = sku_dir.name.strip()
            if not sku:
                continue

            # Archivos de imagen en la carpeta SKU
            image_paths = [
                p
                for p in sku_dir.iterdir()
                if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
            ]
            image_paths.sort(key=_image_order_key)

            if not image_paths:
                stats["skipped_no_images"] += 1
                if dry_run:
                    self.stdout.write(f"  [sin imágenes] {sku}")
                continue

            try:
                product = Product.objects.get(sku=sku)
            except Product.DoesNotExist:
                stats["skipped_no_product"] += 1
                self.stdout.write(self.style.WARNING(f"  [sin producto en BD] {sku}"))
                continue

            existing_count = product.images.count()
            to_add = min(len(image_paths), ProductImage.MAX_IMAGES_PER_PRODUCT)

            if not replace and existing_count >= ProductImage.MAX_IMAGES_PER_PRODUCT:
                stats["skipped_full"] += 1
                if dry_run:
                    self.stdout.write(f"  [ya tiene 4 imágenes] {sku}")
                continue

            if dry_run:
                self.stdout.write(
                    self.style.NOTICE(
                        f"  [dry-run] {sku}: {existing_count} actuales → "
                        f"{'reemplazar con' if replace else 'añadir hasta'} {to_add} imágenes"
                    )
                )
                for i, p in enumerate(image_paths[: ProductImage.MAX_IMAGES_PER_PRODUCT], start=1):
                    self.stdout.write(f"      {i}. {p.name} (is_primary={i == 1})")
                stats["created"] += to_add
                continue

            if replace:
                deleted, _ = product.images.all().delete()
                if deleted:
                    stats["replaced"] += 1
            else:
                # Añadir solo las que falten hasta 4
                slots_left = ProductImage.MAX_IMAGES_PER_PRODUCT - existing_count
                if slots_left <= 0:
                    stats["skipped_full"] += 1
                    continue
                image_paths = image_paths[:slots_left]

            # Crear ProductImage por cada archivo (hasta 4)
            for position, file_path in enumerate(image_paths[: ProductImage.MAX_IMAGES_PER_PRODUCT], start=1):
                if not replace:
                    # Ajustar position para no pisar existentes
                    position = existing_count + position
                    if position > ProductImage.MAX_IMAGES_PER_PRODUCT:
                        break
                is_primary = position == 1
                with open(file_path, "rb") as fh:
                    file_obj = File(fh, name=file_path.name)
                    ProductImage.objects.create(
                        product=product,
                        image=file_obj,
                        alt_text=product.name or "",
                        is_primary=is_primary,
                        position=position,
                    )
                stats["created"] += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  [ok] {sku} pos={position} is_primary={is_primary} ← {file_path.name}")
                )

        self.stdout.write("")
        self.stdout.write("Resumen:")
        self.stdout.write(f"  Creadas: {stats['created']}")
        if stats.get("replaced", 0):
            self.stdout.write(f"  Productos con imágenes reemplazadas: {stats['replaced']}")
        self.stdout.write(f"  Omitidos (sin producto en BD): {stats['skipped_no_product']}")
        self.stdout.write(f"  Omitidos (sin imágenes en carpeta): {stats['skipped_no_images']}")
        self.stdout.write(f"  Omitidos (ya 4 imágenes, sin --replace): {stats['skipped_full']}")
