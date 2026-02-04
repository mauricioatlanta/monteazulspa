# -*- coding: utf-8 -*-
"""
Añade al catálogo el catalítico TWCAT003 con sus imágenes.
Uso: python manage.py add_catalitico_twcat003
"""
import shutil
from decimal import Decimal
from pathlib import Path
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product, ProductImage


ASSETS_PREFIX = "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_"
IMAGE_FILES = [
    ASSETS_PREFIX + "twcat003-72bdbd9c-1dc8-44c5-b5d6-43bc340dd613.png",
    ASSETS_PREFIX + "twcat003_1-f8bee962-a68c-47b7-a5dd-919d512d7577.png",
]
CURSOR_ASSETS = Path(r"C:\Users\Mauricio\.cursor\projects\e-projecto-monteazulspa\assets")
CATEGORY_SLUG = "cataliticos"


class Command(BaseCommand):
    help = "Añade catalítico TWCAT003 al catálogo con imágenes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        base_dir = Path(settings.BASE_DIR)
        media_root = Path(settings.MEDIA_ROOT)
        product_import = media_root / "product_import"
        assets_dir = base_dir / "assets"

        image_paths = []
        for i, name in enumerate(IMAGE_FILES):
            for d in (CURSOR_ASSETS, assets_dir):
                f = d / name
                if f.exists():
                    image_paths.append(f)
                    break
            if not image_paths or len(image_paths) <= i:
                p = product_import / f"TWCAT003_{i+1}.png"
                if p.exists():
                    image_paths.append(p)
        if not image_paths and CURSOR_ASSETS.exists():
            image_paths = sorted(CURSOR_ASSETS.glob("*twcat003*.png"))[:4]

        today = date.today()
        upload_dir = media_root / "products" / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"

        product_data = {
            "sku": "TWCAT003",
            "name": "Catalítico TWCAT003",
            "price": Decimal("0"),
            "cost_price": Decimal("0"),
            "material": "CERAMICO",
        }

        if dry_run:
            self.stdout.write(f"DRY RUN: {product_data['sku']} - {product_data['name']}, {len(image_paths)} imágenes")
            return

        try:
            category = Category.objects.get(slug=CATEGORY_SLUG, is_active=True)
        except Category.DoesNotExist:
            category = Category.objects.create(name="Catalíticos", slug=CATEGORY_SLUG, is_active=True)
            self.stdout.write(self.style.SUCCESS(f"Categoría creada: {category.name}"))

        slug_base = slugify(product_data["name"])[:280]
        slug = slug_base
        n = 0
        while Product.objects.filter(slug=slug).exists():
            n += 1
            slug = f"{slug_base}-{n}"[:280]

        product, created = Product.objects.update_or_create(
            sku=product_data["sku"],
            defaults={
                "name": product_data["name"],
                "slug": slug,
                "category": category,
                "price": product_data["price"],
                "cost_price": product_data["cost_price"],
                "material": product_data["material"],
                "is_active": True,
                "is_publishable": True,
            },
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Producto creado: {product.sku} - {product.name}"))
        else:
            self.stdout.write(f"Producto actualizado: {product.sku}")

        upload_dir.mkdir(parents=True, exist_ok=True)
        ProductImage.objects.filter(product=product).delete()
        for pos, img_path in enumerate(image_paths[:4], start=1):
            ext = img_path.suffix
            dest_name = f"TWCAT003_{pos}{ext}"
            dest_path = upload_dir / dest_name
            shutil.copy2(img_path, dest_path)
            relative_path = f"products/{today.year}/{today.month:02d}/{today.day:02d}/{dest_name}"
            ProductImage.objects.create(
                product=product,
                image=relative_path,
                alt_text="Catalítico TWCAT003, Monteazul SPA",
                is_primary=(pos == 1),
                position=pos,
            )
            self.stdout.write(self.style.SUCCESS(f"  Imagen {pos}: {relative_path}"))

        product.refresh_quality(save=True)
        self.stdout.write(self.style.SUCCESS("Listo: catalítico TWCAT003 con imágenes añadido al catálogo."))
