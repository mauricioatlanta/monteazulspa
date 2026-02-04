# -*- coding: utf-8 -*-
"""
Actualiza los precios de venta de los productos que ya están en el catálogo,
leyendo desde lista precios publico.xlsx. No crea productos nuevos.
Uso: python manage.py update_precios_from_xlsx "ruta/lista precios publico.xlsx"
"""
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand

from apps.catalog.models import Product

# Reutilizar el parseo del Excel
from apps.catalog.management.commands.load_precios_xlsx import _parse_sheet


class Command(BaseCommand):
    help = "Ajusta precios de venta desde Excel solo para productos ya existentes en el catálogo."

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            type=str,
            nargs="?",
            default=r"E:\Usuarios\Mauricio\Descargas\lista precios publico.xlsx",
            help="Ruta al archivo .xlsx",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué precios se actualizarían, sin guardar.",
        )

    def handle(self, *args, **options):
        path = Path(options["path"])
        dry_run = options.get("dry_run", False)

        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Archivo no encontrado: {path}"))
            return

        self.stdout.write(f"Leyendo {path} ...")
        wb = openpyxl.load_workbook(path, read_only=True)

        updated = 0
        skipped = 0
        not_found = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            category_name, items = _parse_sheet(ws)
            if not items:
                continue
            for sku, name, price in items:
                if not sku or price <= 0:
                    continue
                # Buscar producto por SKU exacto o sin guiones/variantes
                product = Product.objects.filter(sku__iexact=sku, is_active=True).first()
                if not product:
                    # Probar variantes: sin espacios, sin guiones
                    sku_alt = sku.replace(" ", "").replace("-", "")
                    product = Product.objects.filter(sku__iexact=sku_alt, is_active=True).first()
                if not product:
                    # Probar por coincidencia parcial (ej. 2.5X6 vs 2X6EXT-REF no)
                    not_found.append((sku, price))
                    skipped += 1
                    continue
                if dry_run:
                    self.stdout.write(f"  {product.sku}: ${product.price} → ${price}")
                else:
                    product.price = price
                    product.save(update_fields=["price"])
                updated += 1

        wb.close()

        if not_found and len(not_found) <= 20:
            self.stdout.write(self.style.WARNING(f"Sin coincidencia en catálogo ({len(not_found)}): {[s for s, p in not_found[:10]]}..."))
        elif not_found:
            self.stdout.write(self.style.WARNING(f"Sin coincidencia en catálogo: {len(not_found)} códigos"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"DRY RUN: se actualizarían {updated} precios. Ejecuta sin --dry-run para guardar."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Listo: {updated} precios de venta actualizados desde el Excel."))
