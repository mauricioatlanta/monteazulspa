# -*- coding: utf-8 -*-
"""
Elimina la(s) imagen(es) del producto Cataliticos Twc: CLF 002-200 2 (SKU CLF-002-200).
Uso: python manage.py eliminar_imagen_clf002200
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductImage


class Command(BaseCommand):
    help = "Elimina las imágenes del producto CLF-002-200 (CLF 002-200 2)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se eliminaría.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        product = Product.objects.filter(sku="CLF-002-200").first()
        if not product:
            product = Product.objects.filter(sku__iexact="CLF-002-200").first()
        if not product:
            self.stderr.write(self.style.ERROR("No se encontró el producto con SKU CLF-002-200."))
            return

        images = list(product.images.all())
        if not images:
            self.stdout.write(self.style.NOTICE(f"El producto {product.sku} ({product.name}) no tiene imágenes."))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Modo dry-run: se eliminarían {len(images)} imagen(es) de {product.sku} ({product.name})."))
            return

        n = product.images.count()
        product.images.all().delete()
        product.refresh_quality(save=True)
        self.stdout.write(self.style.SUCCESS(f"Eliminadas {n} imagen(es) del producto {product.sku} ({product.name})."))
