# -*- coding: utf-8 -*-
"""
Reporta productos que parecen vehiculares pero no tienen ninguna ProductCompatibility activa.
Los productos resueltos por backfill (marca+modelo, solo marca, o multi-aplicación) dejan de aparecer.
Exporta tmp/product_compatibility_gaps.csv.
Uso: python manage.py report_product_compatibility_gaps
"""
import csv
import os
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, VehicleBrand, VehicleModel
from apps.catalog.compatibility_backfill import (
    detect_brand,
    detect_model,
    is_vehicle_specific_product,
)

GAPS_REPORT_PATH = "tmp/product_compatibility_gaps.csv"


class Command(BaseCommand):
    help = "Reporta productos vehiculares sin compatibilidad (CSV en tmp/)."

    def handle(self, *args, **options):
        products_qs = (
            Product.objects.filter(is_active=True, deleted_at__isnull=True)
            .select_related("category")
        )
        candidates = [p for p in products_qs if is_vehicle_specific_product(p)]
        brands_qs = VehicleBrand.objects.all().order_by("name")
        rows = []
        for product in candidates:
            if product.compatibilities.filter(is_active=True).exists():
                continue
            text = f"{product.name} {product.sku}"
            brand, rest = detect_brand(text, brands_qs)
            guessed_brand = brand.name if brand else ""
            guessed_model = ""
            reason = "sin_marca_unica"
            if brand:
                models_qs = VehicleModel.objects.filter(brand=brand).order_by("name")
                model = detect_model(rest or text, brand, models_qs)
                if model:
                    guessed_model = model.name
                    reason = "match_posible_revisar"
                else:
                    reason = "sin_modelo_unico"
            rows.append({
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name[:200],
                "category_slug": product.category.slug or "",
                "guessed_brand": guessed_brand,
                "guessed_model": guessed_model,
                "reason": reason,
            })

        os.makedirs(os.path.dirname(GAPS_REPORT_PATH) or ".", exist_ok=True)
        with open(GAPS_REPORT_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "product_id", "sku", "name", "category_slug",
                "guessed_brand", "guessed_model", "reason",
            ])
            w.writeheader()
            w.writerows(rows)
        self.stdout.write(self.style.SUCCESS(f"Gaps: {len(rows)} productos sin compatibilidad. Reporte: {GAPS_REPORT_PATH}"))
