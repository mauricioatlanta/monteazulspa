# -*- coding: utf-8 -*-
"""
Backfill de ProductCompatibility desde productos del catálogo (Direct Fit / CLF / Ensamble Directo).
Soporta: (1) marca+modelo específico, (2) solo marca = compatibilidad para todos los modelos de esa marca,
(3) múltiples aplicaciones en el nombre (ej. "Hyundai Accent / Kia Rio").
Uso:
  python manage.py backfill_product_compatibility_from_catalog --dry-run
  python manage.py backfill_product_compatibility_from_catalog
  python manage.py backfill_product_compatibility_from_catalog --limit 50
"""
import csv
import os
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import (
    Product,
    ProductCompatibility,
    VehicleBrand,
    VehicleModel,
)
from apps.catalog.compatibility_backfill import parse_vehicle_applications

REPORT_PATH = "tmp/product_compatibility_backfill_report.csv"
YEAR_FROM_DEFAULT = 1900
YEAR_TO_DEFAULT = 2100


class Command(BaseCommand):
    help = "Crea ProductCompatibility para productos vehiculares (marca+modelo, solo marca, o multi-aplicación)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guardar; solo listar y generar CSV.")
        parser.add_argument("--limit", type=int, default=0, help="Máximo de productos a procesar (0 = todos).")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        products_qs = (
            Product.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
                is_publishable=True,
                category__slug="cataliticos-ensamble-directo",
            )
            .select_related("category")
            .order_by("sku")
        )

        brands_qs = VehicleBrand.objects.all().order_by("name")
        if not brands_qs.exists():
            self.stderr.write(self.style.ERROR("No hay VehicleBrand en la base. Ejecuta load_vehicles_chile."))
            return

        candidates = list(products_qs)
        if limit:
            candidates = candidates[:limit]

        os.makedirs(os.path.dirname(REPORT_PATH) or ".", exist_ok=True)
        rows = []
        stats = {"candidatos": len(candidates), "creados": 0, "ya_existentes": 0, "descartados": 0}

        for product in candidates:
            text = f"{product.name} {product.sku}"
            pairs = parse_vehicle_applications(text, brands_qs)
            if not pairs:
                stats["descartados"] += 1
                rows.append({
                    "product_id": product.id,
                    "sku": product.sku,
                    "name": product.name[:200],
                    "category_slug": product.category.slug or "",
                    "detected_brand": "",
                    "detected_model": "",
                    "action": "descartado",
                    "reason": "sin_marca_unica",
                })
                continue

            brand_labels = []
            model_labels = []
            for brand, model in pairs:
                brand_labels.append(brand.name)
                model_labels.append(model.name if model else "(todos)")
            detected_brand = "; ".join(brand_labels)
            detected_model = "; ".join(model_labels)

            created_this = 0
            existing_this = 0
            for brand, model in pairs:
                if model is not None:
                    if ProductCompatibility.objects.filter(
                        product=product,
                        brand=brand,
                        model=model,
                        is_active=True,
                    ).exists():
                        existing_this += 1
                    else:
                        if not dry_run:
                            with transaction.atomic():
                                ProductCompatibility.objects.create(
                                    product=product,
                                    brand=brand,
                                    model=model,
                                    year_from=YEAR_FROM_DEFAULT,
                                    year_to=YEAR_TO_DEFAULT,
                                    engine=None,
                                    is_active=True,
                                )
                        created_this += 1
                else:
                    for m in VehicleModel.objects.filter(brand=brand).order_by("name"):
                        if ProductCompatibility.objects.filter(
                            product=product,
                            brand=brand,
                            model=m,
                            is_active=True,
                        ).exists():
                            existing_this += 1
                        else:
                            if not dry_run:
                                with transaction.atomic():
                                    ProductCompatibility.objects.create(
                                        product=product,
                                        brand=brand,
                                        model=m,
                                        year_from=YEAR_FROM_DEFAULT,
                                        year_to=YEAR_TO_DEFAULT,
                                        engine=None,
                                        is_active=True,
                                    )
                            created_this += 1

            stats["creados"] += created_this
            stats["ya_existentes"] += existing_this
            action = "creado" if not dry_run else "creado_dry_run"
            if created_this == 0 and existing_this > 0:
                action = "existente"
            rows.append({
                "product_id": product.id,
                "sku": product.sku,
                "name": product.name[:200],
                "category_slug": product.category.slug or "",
                "detected_brand": detected_brand,
                "detected_model": detected_model,
                "action": action,
                "reason": "" if created_this or existing_this else "",
            })

        with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "product_id", "sku", "name", "category_slug",
                "detected_brand", "detected_model", "action", "reason",
            ])
            w.writeheader()
            w.writerows(rows)

        self.stdout.write(f"Candidatos: {stats['candidatos']}")
        self.stdout.write(f"Creados: {stats['creados']}")
        self.stdout.write(f"Ya existentes: {stats['ya_existentes']}")
        self.stdout.write(f"Descartados: {stats['descartados']}")
        self.stdout.write(self.style.SUCCESS(f"Reporte: {REPORT_PATH}"))
        if dry_run and stats["creados"]:
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para crear las compatibilidades."))
