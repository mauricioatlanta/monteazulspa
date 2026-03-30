# -*- coding: utf-8 -*-
"""
Backfill de ProductCompatibility para productos CLF / Ensamble Directo (v2).

Usa parser v2 que:
- Detecta mejor marca/modelo desde name y sku (alias, normalización).
- Normaliza typos tipo CLFOO2 -> CLF002.
- Separa: EXACTA (marca+modelo), BAJA (solo marca), DESCARTADO (código/medida).
- No inventa compatibilidades sin evidencia.
- Soporta múltiples marcas (ej. Hyundai Accent / Kia Rio).

Uso:
  python manage.py backfill_clf_compatibility --dry-run
  python manage.py backfill_clf_compatibility
  python manage.py backfill_clf_compatibility --all
  python manage.py backfill_clf_compatibility --limit 20
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
from apps.catalog.utils.clf_backfill_v2 import classify_clf_product

REPORT_PATH = "tmp/backfill_clf_compatibility_report.csv"

CLF_CATEGORY_SLUGS = ("cataliticos-clf", "cataliticos-ensamble-directo")


def is_clf_product(product) -> bool:
    """True si el producto es CLF/Ensamble Directo por categoría o SKU (incl. tipo-original con CLF)."""
    slug = (getattr(product.category, "slug", None) or "").lower()
    if slug in CLF_CATEGORY_SLUGS:
        return True
    sku = (product.sku or "").upper()
    if "CLF" not in sku:
        return False
    return "cataliticos" in slug


class Command(BaseCommand):
    help = (
        "Crea ProductCompatibility para productos CLF (v2: parser mejorado, "
        "solo cuando hay evidencia de marca/modelo). Genera reporte CSV."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No guardar; solo listar y generar CSV.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Máximo de productos a procesar (0 = todos).",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Procesar todos los CLF; por defecto solo los que no tienen ninguna compatibilidad.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]
        process_all = options["all"]

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        products_qs = (
            Product.objects.filter(
                is_active=True,
                deleted_at__isnull=True,
            )
            .select_related("category")
            .order_by("sku")
        )
        candidates = [p for p in products_qs if is_clf_product(p)]
        if not process_all:
            candidates = [p for p in candidates if not p.compatibilities.filter(is_active=True).exists()]
        if limit:
            candidates = candidates[:limit]

        if not VehicleBrand.objects.exists():
            self.stderr.write(
                self.style.ERROR("No hay VehicleBrand en la base. Ejecuta load_vehicles_chile.")
            )
            return

        os.makedirs(os.path.dirname(REPORT_PATH) or ".", exist_ok=True)
        rows = []
        stats = {"candidatos": len(candidates), "creados": 0, "ya_existentes": 0, "descartados": 0, "errores": 0}

        for product in candidates:
            result = classify_clf_product(product.name, product.sku)

            row = {
                "product_id": product.id,
                "sku": product.sku,
                "name": (product.name or "")[:200],
                "category_slug": getattr(product.category, "slug", "") or "",
                "detected_brand": result.detected_brand or "",
                "detected_model": result.detected_model or "",
                "precision": result.precision or "",
                "action": result.action,
                "reason": result.reason,
                "year_from": result.year_from if result.year_from is not None else "",
                "year_to": result.year_to if result.year_to is not None else "",
            }
            rows.append(row)

            if result.action != "crear":
                stats["descartados"] += 1
                continue

            year_from = result.year_from or 1900
            year_to = result.year_to or 2100
            confidence = result.precision or "BAJA"
            created_this = 0
            existing_this = 0
            had_error = False
            error_reason = ""

            for brand_name, model_name in result.applications:
                if had_error:
                    break
                brand_obj = VehicleBrand.objects.filter(name__iexact=brand_name).first()
                if not brand_obj:
                    continue

                # Regla fija: NUNCA iterar sobre VehicleModel cuando no hay modelo.
                # Solo marca → UNA fila con model=None. Modelo concreto → UNA fila con ese model.
                if model_name and model_name != "(todos)":
                    model_obj = VehicleModel.objects.filter(
                        brand=brand_obj, name__iexact=model_name
                    ).first()
                    if not model_obj:
                        continue
                    if ProductCompatibility.objects.filter(
                        product=product,
                        brand=brand_obj,
                        model=model_obj,
                        is_active=True,
                    ).exists():
                        existing_this += 1
                        continue
                    if dry_run:
                        created_this += 1
                        continue
                    try:
                        with transaction.atomic():
                            ProductCompatibility.objects.create(
                                product=product,
                                brand=brand_obj,
                                model=model_obj,
                                year_from=year_from,
                                year_to=year_to,
                                engine=None,
                                displacement_cc=None,
                                fuel_type=None,
                                notes="CLF backfill v2 desde nombre/SKU",
                                confidence=confidence,
                                is_active=True,
                            )
                        created_this += 1
                    except Exception as e:
                        stats["errores"] += 1
                        had_error = True
                        error_reason = str(e)[:200]
                        row["action"] = "error"
                        row["reason"] = error_reason
                        break
                else:
                    # Una sola fila: brand + model=None, confidence=BAJA (compatibilidad amplia por marca).
                    if ProductCompatibility.objects.filter(
                        product=product,
                        brand=brand_obj,
                        model__isnull=True,
                        is_active=True,
                    ).exists():
                        existing_this += 1
                        continue
                    if dry_run:
                        created_this += 1
                        continue
                    try:
                        with transaction.atomic():
                            ProductCompatibility.objects.create(
                                product=product,
                                brand=brand_obj,
                                model=None,
                                year_from=year_from,
                                year_to=year_to,
                                engine=None,
                                displacement_cc=None,
                                fuel_type=None,
                                notes="CLF backfill v2 compatibilidad amplia por marca",
                                confidence="BAJA",
                                is_active=True,
                            )
                        created_this += 1
                    except Exception as e:
                        stats["errores"] += 1
                        had_error = True
                        error_reason = str(e)[:200]
                        row["action"] = "error"
                        row["reason"] = error_reason
                        break

            stats["creados"] += created_this
            stats["ya_existentes"] += existing_this
            if not had_error and result.action == "crear":
                if dry_run and created_this:
                    row["action"] = "creado_dry_run"
                elif created_this == 0 and existing_this > 0:
                    row["action"] = "existente"
                elif not dry_run and created_this:
                    row["action"] = "creado"

        with open(REPORT_PATH, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "product_id",
                    "sku",
                    "name",
                    "category_slug",
                    "detected_brand",
                    "detected_model",
                    "precision",
                    "action",
                    "reason",
                    "year_from",
                    "year_to",
                ],
            )
            w.writeheader()
            w.writerows(rows)

        self.stdout.write(f"Candidatos: {stats['candidatos']}")
        self.stdout.write(f"Creados: {stats['creados']}")
        self.stdout.write(f"Ya existentes: {stats['ya_existentes']}")
        self.stdout.write(f"Descartados: {stats['descartados']}")
        if stats["errores"]:
            self.stdout.write(self.style.ERROR(f"Errores: {stats['errores']}"))
        self.stdout.write(self.style.SUCCESS(f"Reporte: {REPORT_PATH}"))
        if dry_run and stats["creados"]:
            self.stdout.write(
                self.style.WARNING("Ejecuta sin --dry-run para crear las compatibilidades.")
            )
