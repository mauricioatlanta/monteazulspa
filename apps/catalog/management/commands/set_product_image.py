# -*- coding: utf-8 -*-
"""
Asigna una imagen a un producto existente por SKU.
Uso: python manage.py set_product_image LT043 --image ruta/imagen.png
"""
import shutil
from pathlib import Path
from datetime import date

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductImage


class Command(BaseCommand):
    help = "Asigna una imagen a un producto por SKU."

    def add_arguments(self, parser):
        parser.add_argument("sku", type=str, help="SKU del producto (ej: LT043)")
        parser.add_argument("--image", type=str, default=None, help="Ruta a la imagen")
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def handle(self, *args, **options):
        sku = (options["sku"] or "").strip().upper()
        if not sku:
            self.stdout.write(self.style.ERROR("Indica el SKU del producto."))
            return

        try:
            product = Product.objects.get(sku__iexact=sku, is_active=True)
        except Product.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"No existe un producto activo con SKU '{sku}'."))
            return

        base_dir = Path(settings.BASE_DIR)
        media_root = Path(settings.MEDIA_ROOT)
        img_path = None
        if options.get("image"):
            p = Path(options["image"])
            if p.exists():
                img_path = p
            else:
                self.stdout.write(self.style.WARNING(f"Imagen no encontrada: {p}"))
        if not img_path:
            # Ruta por defecto para LT043 (Cursor assets)
            for candidate in [
                media_root / "product_import" / "LT043.png",
                base_dir / "media" / "product_import" / "LT043.png",
                base_dir
                / "assets"
                / "c__Users_Mauricio_AppData_Roaming_Cursor_User_workspaceStorage_ff5ad3f650ba888a9227a08d3bf3ffc1_images_LT043-4dec08ab-2835-49fe-b5d7-cfb79d28b47c.png",
            ]:
                if candidate.exists():
                    img_path = candidate
                    break

        if not img_path or not img_path.exists():
            self.stdout.write(self.style.ERROR("No se encontró la imagen. Usa --image ruta/imagen.png"))
            return

        today = date.today()
        upload_dir = media_root / "products" / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
        dest_name = f"{sku.lower()}.png"
        relative_path = f"products/{today.year}/{today.month:02d}/{today.day:02d}/{dest_name}"

        if options.get("dry_run"):
            self.stdout.write(f"DRY RUN: asignar imagen a {product.sku} - {product.name}")
            self.stdout.write(f"  Origen: {img_path}")
            self.stdout.write(f"  Destino: {relative_path}")
            return

        upload_dir.mkdir(parents=True, exist_ok=True)
        dest_path = upload_dir / dest_name
        shutil.copy2(img_path, dest_path)

        ProductImage.objects.filter(product=product, position=1).delete()
        ProductImage.objects.create(
            product=product,
            image=relative_path,
            alt_text=f"{product.name} - Calidad superior",
            is_primary=True,
            position=1,
        )
        product.refresh_quality(save=True)

        self.stdout.write(self.style.SUCCESS(f"Imagen asignada a {product.sku} - {product.name}"))
        self.stdout.write(self.style.SUCCESS(f"  {relative_path}"))
