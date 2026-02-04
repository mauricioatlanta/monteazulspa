# -*- coding: utf-8 -*-
"""
Añade/actualiza en el catálogo los flexibles reforzados con nipple (equiv. con extensión) 2x6 y 2x8.
En la lista de precios: "flex reforzado with napples" 2X6 y 2X8 = mismos productos.
Uso: python manage.py add_flex_reforzado
"""
import shutil
from decimal import Decimal
from pathlib import Path
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product, ProductImage


# 2x6 y 2x8 reforzados con nipple = 2x6 y 2x8 con extensión (mismo producto)
PRODUCTS = [
    {
        "sku": "2X6EXT-REF",
        "name": "Flexible reforzado con nipple 2\" x 6\" (con extensión)",
        "price": Decimal("24990"),
        "cost_price": Decimal("0"),
        "weight": Decimal("0.55"),
        "volume": Decimal("0.55"),
        "image_filename": "2x6extension.png",
        "alt_text": "Flexible reforzado con nipple 2 x 6 pulgadas, calidad superior",
    },
    {
        "sku": "2X8EXT-REF",
        "name": "Flexible reforzado con nipple 2\" x 8\" (con extensión)",
        "price": Decimal("27990"),
        "cost_price": Decimal("0"),
        "weight": Decimal("0.65"),
        "volume": Decimal("0.65"),
        "image_filename": "2x8extension.png",
        "alt_text": "Flexible reforzado con nipple 2 x 8 pulgadas, calidad superior",
    },
]

CATEGORY_SLUG = "tubos-flexibles"


class Command(BaseCommand):
    help = "Añade flexibles reforzados con extensión 2x6 y 2x8 al catálogo."

    def add_arguments(self, parser):
        parser.add_argument("--img-2x6", type=str, default=None, help="Ruta imagen 2x6 extensión reforzado")
        parser.add_argument("--img-2x8", type=str, default=None, help="Ruta imagen 2x8 extensión reforzado")
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def _find_image(self, options_key, patterns, candidates):
        path_arg = self.options.get(options_key)
        if path_arg:
            p = Path(path_arg)
            if p.exists():
                return p
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def handle(self, *args, **options):
        self.options = options
        dry_run = options["dry_run"]
        base_dir = Path(settings.BASE_DIR)
        media_root = Path(settings.MEDIA_ROOT)

        candidates_2x6 = [
            media_root / "product_import" / "2x6extension.png",
            base_dir / "media" / "product_import" / "2x6extension.png",
            base_dir
            / "assets"
            / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_2x6extension-a6217b73-ebda-45bb-b16d-5463c2050783.png",
        ]
        candidates_2x8 = [
            media_root / "product_import" / "2x8extension.png",
            base_dir / "media" / "product_import" / "2x8extension.png",
            base_dir
            / "assets"
            / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_2X8extension-1c24be1a-c1f9-49ef-a37e-b62c5368faae.png",
        ]

        img_2x6 = None
        if options.get("img_2x6"):
            p = Path(options["img_2x6"])
            if p.exists():
                img_2x6 = p
        if not img_2x6:
            for c in candidates_2x6:
                if c.exists():
                    img_2x6 = c
                    break

        img_2x8 = None
        if options.get("img_2x8"):
            p = Path(options["img_2x8"])
            if p.exists():
                img_2x8 = p
        if not img_2x8:
            for c in candidates_2x8:
                if c.exists():
                    img_2x8 = c
                    break

        today = date.today()
        upload_dir = media_root / "products" / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"

        if dry_run:
            self.stdout.write("DRY RUN: flexibles reforzados 2X6EXT-REF y 2X8EXT-REF")
            self.stdout.write(f"  Imagen 2x6: {img_2x6}")
            self.stdout.write(f"  Imagen 2x8: {img_2x8}")
            return

        try:
            category = Category.objects.get(slug=CATEGORY_SLUG, is_active=True)
        except Category.DoesNotExist:
            category = Category.objects.create(
                name="Tubos flexibles",
                slug=CATEGORY_SLUG,
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f"Categoría creada: {category.name}"))

        image_paths = [img_2x6, img_2x8]
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
                self.stdout.write(self.style.WARNING(f"  Sin imagen para {sku}"))

            product.refresh_quality(save=True)

        self.stdout.write(self.style.SUCCESS("Listo: flexibles reforzados con extensión añadidos al catálogo."))
