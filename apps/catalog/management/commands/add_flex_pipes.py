# -*- coding: utf-8 -*-
"""
Añade al catálogo los tubos flexibles de escape 2x6 y 2x8 con sus imágenes.
Uso:
  python manage.py add_flex_pipes
  python manage.py add_flex_pipes --img-2x6 ruta/2x6.png --img-2x8 ruta/2x8.png
"""
import shutil
from decimal import Decimal
from pathlib import Path
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product, ProductImage


# Rutas por defecto donde buscar las imágenes (Cursor workspace assets)
DEFAULT_IMAGE_PATHS = [
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    / "assets"
    / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_2x6ext-a9fc82b4-2bb3-482c-bf94-f6e63d9b4373.png",
    Path(__file__).resolve().parent.parent.parent.parent.parent.parent
    / "assets"
    / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_2X8EXT-e1a68e8d-cf51-4c40-8631-8ae9f86277fb.png",
]

PRODUCTS = [
    {
        "sku": "2X6EXT",
        "name": "Tubo flexible de escape 2\" x 6\"",
        "price": Decimal("19990"),
        "cost_price": Decimal("0"),
        "weight": Decimal("0.5"),
        "volume": Decimal("0.5"),
        "image_filename": "2x6ext.png",
        "alt_text": "Tubo flexible escape 2 pulgadas x 6 pulgadas, acero inoxidable",
    },
    {
        "sku": "2X8EXT",
        "name": "Tubo flexible de escape 2\" x 8\"",
        "price": Decimal("22990"),
        "cost_price": Decimal("0"),
        "weight": Decimal("0.6"),
        "volume": Decimal("0.6"),
        "image_filename": "2x8ext.png",
        "alt_text": "Tubo flexible escape 2 pulgadas x 8 pulgadas, acero inoxidable",
    },
]

CATEGORY_NAME = "Tubos flexibles"
CATEGORY_SLUG = "tubos-flexibles"


def find_image(base_dir: Path, patterns: list) -> Path | None:
    """Busca un archivo en base_dir que coincida con alguno de los nombres/patrones."""
    if not base_dir.exists():
        return None
    for p in patterns:
        path = base_dir / p
        if path.exists():
            return path
    for child in base_dir.rglob("*.png"):
        if any(pat in child.name.lower() for pat in ["2x6ext", "2x6"]):
            return child
    return None


def find_image_2x8(base_dir: Path, patterns: list) -> Path | None:
    if not base_dir.exists():
        return None
    for p in patterns:
        path = base_dir / p
        if path.exists():
            return path
    for child in base_dir.rglob("*.png"):
        if any(pat in child.name.lower() for pat in ["2x8ext", "2x8"]):
            return child
    return None


class Command(BaseCommand):
    help = "Añade tubos flexibles 2x6 y 2x8 al catálogo con imágenes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--img-2x6",
            type=str,
            default=None,
            help="Ruta a la imagen del tubo 2x6",
        )
        parser.add_argument(
            "--img-2x8",
            type=str,
            default=None,
            help="Ruta a la imagen del tubo 2x8",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se haría, sin crear ni copiar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        base_dir = Path(settings.BASE_DIR)
        media_root = Path(settings.MEDIA_ROOT)

        # Resolver rutas de imágenes
        img_2x6_path = None
        if options.get("img_2x6"):
            p = Path(options["img_2x6"])
            if p.exists():
                img_2x6_path = p
            else:
                self.stdout.write(self.style.WARNING(f"No se encontró imagen 2x6: {p}"))
        if not img_2x6_path:
            for candidate in [
                media_root / "product_import" / "2x6ext.png",
                base_dir / "media" / "product_import" / "2x6ext.png",
                base_dir / "assets" / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_2x6ext-a9fc82b4-2bb3-482c-bf94-f6e63d9b4373.png",
            ]:
                if candidate.exists():
                    img_2x6_path = candidate
                    break
            if not img_2x6_path:
                img_2x6_path = find_image(base_dir, ["2x6ext.png", "2x6ext-*.png"])

        img_2x8_path = None
        if options.get("img_2x8"):
            p = Path(options["img_2x8"])
            if p.exists():
                img_2x8_path = p
            else:
                self.stdout.write(self.style.WARNING(f"No se encontró imagen 2x8: {p}"))
        if not img_2x8_path:
            for candidate in [
                media_root / "product_import" / "2x8ext.png",
                base_dir / "media" / "product_import" / "2x8ext.png",
                base_dir / "assets" / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_2X8EXT-e1a68e8d-cf51-4c40-8631-8ae9f86277fb.png",
            ]:
                if candidate.exists():
                    img_2x8_path = candidate
                    break
            if not img_2x8_path:
                img_2x8_path = find_image_2x8(base_dir, ["2x8ext.png", "2X8EXT-*.png"])

        today = date.today()
        upload_dir = media_root / "products" / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"

        if dry_run:
            self.stdout.write(f"DRY RUN: categoría '{CATEGORY_NAME}', productos 2X6EXT y 2X8EXT")
            self.stdout.write(f"  Imagen 2x6: {img_2x6_path}")
            self.stdout.write(f"  Imagen 2x8: {img_2x8_path}")
            self.stdout.write(f"  Destino imágenes: {upload_dir}")
            return

        # Crear categoría
        category, created = Category.objects.get_or_create(
            slug=CATEGORY_SLUG,
            defaults={"name": CATEGORY_NAME, "is_active": True},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Categoría creada: {category.name}"))

        image_paths = [img_2x6_path, img_2x8_path]
        for i, prod_data in enumerate(PRODUCTS):
            sku = prod_data["sku"]
            img_path = image_paths[i] if i < len(image_paths) else None

            slug_base = slugify(prod_data["name"])[:280]
            slug = slug_base
            cnt = 0
            while Product.objects.filter(slug=slug).exists():
                cnt += 1
                slug = f"{slug_base}-{cnt}"[:280]

            product, created = Product.objects.update_or_create(
                sku=sku,
                defaults={
                    "name": prod_data["name"],
                    "slug": slug,
                    "category": category,
                    "price": prod_data["price"],
                    "cost_price": prod_data["cost_price"],
                    "weight": prod_data["weight"],
                    "volume": prod_data["volume"],
                    "material": "INOX",
                    "install_type": "SOLDADURA",
                    "is_active": True,
                    "is_publishable": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Producto creado: {product.sku} - {product.name}"))
            else:
                self.stdout.write(f"Producto actualizado: {product.sku}")

            if img_path and img_path.exists():
                upload_dir.mkdir(parents=True, exist_ok=True)
                dest_name = prod_data["image_filename"]
                dest_path = upload_dir / dest_name
                shutil.copy2(img_path, dest_path)
                relative_path = f"products/{today.year}/{today.month:02d}/{today.day:02d}/{dest_name}"

                # Eliminar imagen anterior en posición 1 si existe
                ProductImage.objects.filter(product=product, position=1).delete()
                ProductImage.objects.create(
                    product=product,
                    image=relative_path,
                    alt_text=prod_data["alt_text"],
                    is_primary=True,
                    position=1,
                )
                self.stdout.write(self.style.SUCCESS(f"  Imagen asignada: {relative_path}"))
            else:
                self.stdout.write(self.style.WARNING(f"  Sin imagen para {sku} (ruta no encontrada)"))

            product.refresh_quality(save=True)

        self.stdout.write(self.style.SUCCESS("Listo: tubos flexibles añadidos al catálogo."))
