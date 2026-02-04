# -*- coding: utf-8 -*-
"""
Añade al catálogo el catalítico CAT-001 (TWG Catalytic Converter) con sus imágenes.
Según el nombre/código de la imagen: COD: CAT-001.
Uso: python manage.py add_catalitico_cat001
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
    "sku": "CAT-001",
    "name": "Catalítico TWG CAT-001",
    "price": Decimal("0"),  # ajustar en admin
    "cost_price": Decimal("0"),
    "weight": None,
    "volume": None,
    "alt_text": "Catalítico TWG, Monteazul SPA",
}

# Imágenes: en Cursor assets el nombre incluye prefijo "c__Users_..._images_"
ASSETS_PREFIX = "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_"
IMAGE_CANDIDATES = [
    ASSETS_PREFIX + "TWCAT052-6eabf84c-2720-4045-8e6c-9ba2702dfef9.png",
    ASSETS_PREFIX + "TWCAT052_1-bcdd7c76-45a1-4ef5-8a76-89a1d0c405a6.png",
    ASSETS_PREFIX + "TWCAT052_2-bd8969df-3f39-4e5c-92a0-551ac59002c2.png",
]
CURSOR_ASSETS_DIR = Path(r"C:\Users\Mauricio\.cursor\projects\e-projecto-monteazulspa\assets")

CATEGORY_SLUG = "cataliticos"


class Command(BaseCommand):
    help = "Añade el catalítico CAT-001 al catálogo con imágenes."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        base_dir = Path(settings.BASE_DIR)
        media_root = Path(settings.MEDIA_ROOT)
        product_import = media_root / "product_import"
        assets_dir = base_dir / "assets"
        cursor_assets = CURSOR_ASSETS_DIR

        image_paths = []
        for i in range(1, 4):
            p = product_import / f"CAT001_{i}.png"
            if p.exists():
                image_paths.append(p)
            elif i <= len(IMAGE_CANDIDATES):
                for d in (cursor_assets, assets_dir):
                    f = d / IMAGE_CANDIDATES[i - 1]
                    if f.exists():
                        image_paths.append(f)
                        break
        if not image_paths and cursor_assets.exists():
            image_paths = sorted(cursor_assets.glob("*TWCAT052*.png"))[:4]
        if not image_paths and assets_dir.exists():
            image_paths = sorted(assets_dir.glob("*TWCAT052*.png"))[:4]

        today = date.today()
        upload_dir = media_root / "products" / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"

        if dry_run:
            self.stdout.write(f"DRY RUN: producto {PRODUCT['sku']} - {PRODUCT['name']}")
            self.stdout.write(f"  Imágenes encontradas: {len(image_paths)}")
            return

        try:
            category = Category.objects.get(slug=CATEGORY_SLUG, is_active=True)
        except Category.DoesNotExist:
            category = Category.objects.create(name="Catalíticos", slug=CATEGORY_SLUG, is_active=True)
            self.stdout.write(self.style.SUCCESS(f"Categoría creada: {category.name}"))

        slug_base = slugify(PRODUCT["name"])[:280]
        slug = slug_base
        cnt = 0
        while Product.objects.filter(slug=slug).exists():
            cnt += 1
            slug = f"{slug_base}-{cnt}"[:280]

        defaults = {
            "name": PRODUCT["name"],
            "slug": slug,
            "category": category,
            "price": PRODUCT["price"],
            "cost_price": PRODUCT["cost_price"],
            "material": "CERAMICO",
            "is_active": True,
            "is_publishable": True,
        }
        if PRODUCT.get("weight") is not None:
            defaults["weight"] = PRODUCT["weight"]
        if PRODUCT.get("volume") is not None:
            defaults["volume"] = PRODUCT["volume"]

        product, created = Product.objects.update_or_create(
            sku=PRODUCT["sku"],
            defaults=defaults,
        )
        if created:
            self.stdout.write(self.style.SUCCESS(f"Producto creado: {product.sku} - {product.name}"))
        else:
            self.stdout.write(f"Producto actualizado: {product.sku}")

        upload_dir.mkdir(parents=True, exist_ok=True)
        ProductImage.objects.filter(product=product).delete()
        for pos, img_path in enumerate(image_paths[:4], start=1):
            ext = img_path.suffix
            dest_name = f"CAT001_{pos}{ext}"
            dest_path = upload_dir / dest_name
            shutil.copy2(img_path, dest_path)
            relative_path = f"products/{today.year}/{today.month:02d}/{today.day:02d}/{dest_name}"
            ProductImage.objects.create(
                product=product,
                image=relative_path,
                alt_text=PRODUCT.get("alt_text", ""),
                is_primary=(pos == 1),
                position=pos,
            )
            self.stdout.write(self.style.SUCCESS(f"  Imagen {pos}: {relative_path}"))

        product.refresh_quality(save=True)
        self.stdout.write(self.style.SUCCESS("Listo: catalítico CAT-001 añadido al catálogo."))
