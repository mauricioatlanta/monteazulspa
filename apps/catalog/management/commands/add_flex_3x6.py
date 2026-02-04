# -*- coding: utf-8 -*-
"""
Añade al catálogo el tubo flexible 3" x 6" con su imagen.
Uso: python manage.py add_flex_3x6 [--image ruta/imagen.png]
"""
import shutil
from decimal import Decimal
from pathlib import Path
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product, ProductImage


PRODUCT = {
    "sku": "3X6",
    "name": "Tubo flexible 3\" x 6\"",
    "price": Decimal("22990"),
    "cost_price": Decimal("0"),
    "weight": Decimal("0.6"),
    "volume": Decimal("0.6"),
    "image_filename": "3x6.png",
    "alt_text": "Tubo flexible 3 x 6 pulgadas, Monteazul SPA",
}

CATEGORY_SLUG = "tubos-flexibles"


class Command(BaseCommand):
    help = "Añade el flexible 3x6 al catálogo con imagen."

    def add_arguments(self, parser):
        parser.add_argument("--image", type=str, default=None, help="Ruta a la imagen del flexible 3x6")
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        base_dir = Path(settings.BASE_DIR)
        media_root = Path(settings.MEDIA_ROOT)

        img_path = None
        if options.get("image"):
            p = Path(options["image"])
            if p.exists():
                img_path = p
        if not img_path:
            for candidate in [
                media_root / "product_import" / "3x6.png",
                base_dir / "media" / "product_import" / "3x6.png",
                base_dir
                / "assets"
                / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_3X6-5e174f73-dcaf-449a-8dd5-8b6cebd5d66f.png",
            ]:
                if candidate.exists():
                    img_path = candidate
                    break

        today = date.today()
        upload_dir = media_root / "products" / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"

        if dry_run:
            self.stdout.write(f"DRY RUN: producto {PRODUCT['sku']} - {PRODUCT['name']}")
            self.stdout.write(f"  Imagen: {img_path}")
            return

        try:
            category = Category.objects.get(slug=CATEGORY_SLUG, is_active=True)
        except Category.DoesNotExist:
            category = Category.objects.create(name="Tubos flexibles", slug=CATEGORY_SLUG, is_active=True)
            self.stdout.write(self.style.SUCCESS(f"Categoría creada: {category.name}"))

        slug_base = slugify(PRODUCT["name"])[:280]
        slug = slug_base
        cnt = 0
        while Product.objects.filter(slug=slug).exists():
            cnt += 1
            slug = f"{slug_base}-{cnt}"[:280]

        product, created = Product.objects.update_or_create(
            sku=PRODUCT["sku"],
            defaults={
                "name": PRODUCT["name"],
                "slug": slug,
                "category": category,
                "price": PRODUCT["price"],
                "cost_price": PRODUCT["cost_price"],
                "weight": PRODUCT["weight"],
                "volume": PRODUCT["volume"],
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
            dest_name = PRODUCT["image_filename"]
            dest_path = upload_dir / dest_name
            shutil.copy2(img_path, dest_path)
            relative_path = f"products/{today.year}/{today.month:02d}/{today.day:02d}/{dest_name}"
            ProductImage.objects.filter(product=product, position=1).delete()
            ProductImage.objects.create(
                product=product,
                image=relative_path,
                alt_text=PRODUCT["alt_text"],
                is_primary=True,
                position=1,
            )
            self.stdout.write(self.style.SUCCESS(f"  Imagen asignada: {relative_path}"))
        else:
            self.stdout.write(self.style.WARNING("  Sin imagen (usa --image ruta/imagen.png)"))

        product.refresh_quality(save=True)
        self.stdout.write(self.style.SUCCESS("Listo: flexible 3x6 añadido al catálogo."))
