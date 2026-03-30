# -*- coding: utf-8 -*-
"""
Limpia compatibilidades que fueron guardadas como expansión masiva (una fila por
cada modelo de la marca) cuando debían ser una sola fila "compatibilidad amplia por marca"
con model=None.

Para cada producto indicado:
- Elimina todas las ProductCompatibility del producto.
- Crea UNA sola ProductCompatibility con brand=<marca>, model=None, confidence=BAJA.

Uso:
  python manage.py cleanup_clf_brand_wide_compatibilities --dry-run
  python manage.py cleanup_clf_brand_wide_compatibilities
  python manage.py cleanup_clf_brand_wide_compatibilities --list
  python manage.py cleanup_clf_brand_wide_compatibilities --sku CLF01 --brand Peugeot
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Product, ProductCompatibility, VehicleBrand

# SKUs que se sabe que son "solo marca" y fueron contaminados por expansión masiva
# Mapeo: sku (exacto o comienza con) -> nombre de marca canónico
DEFAULT_SKU_BRAND_MAP = {
    "CLF03": "Hyundai",
    "CLFO36-AUDI": "Audi",
    "CLF02": "BMW",
    "CLF01": "Peugeot",
}


class Command(BaseCommand):
    help = (
        "Elimina compatibilidades expandidas por modelo y crea una sola "
        "compatibilidad amplia (model=None) por producto/SKU indicado."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo listar qué se haría; no borrar ni crear.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Listar compatibilidades actuales de los SKUs por defecto y salir.",
        )
        parser.add_argument(
            "--sku",
            type=str,
            action="append",
            dest="skus",
            help="SKU a limpiar (puede repetirse). Si no se da, se usan los por defecto.",
        )
        parser.add_argument(
            "--brand",
            type=str,
            action="append",
            dest="brands",
            help="Marca para el SKU anterior (mismo orden que --sku). Requerido si usas --sku.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        list_only = options["list"]
        custom_skus = options["skus"] or []
        custom_brands = options["brands"] or []

        if list_only:
            self._list_compatibilities(DEFAULT_SKU_BRAND_MAP)
            return

        if custom_skus:
            if len(custom_brands) != len(custom_skus):
                self.stderr.write(
                    self.style.ERROR(
                        "Debes pasar el mismo número de --sku y --brand "
                        "(ej. --sku CLF03 --brand Hyundai --sku CLF02 --brand BMW)."
                    )
                )
                return
            sku_brand_map = dict(zip(custom_skus, custom_brands))
        else:
            sku_brand_map = DEFAULT_SKU_BRAND_MAP

        products = list(
            Product.objects.filter(sku__in=sku_brand_map.keys()).select_related("category")
        )
        if not products:
            self.stdout.write("No se encontraron productos con SKU en: %s" % list(sku_brand_map.keys()))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        for product in products:
            brand_name = sku_brand_map.get(product.sku)
            if not brand_name:
                continue
            brand_obj = VehicleBrand.objects.filter(name__iexact=brand_name).first()
            if not brand_obj:
                self.stderr.write(
                    self.style.ERROR("Marca no encontrada: %s (producto %s)" % (brand_name, product.sku))
                )
                continue
            count_before = product.compatibilities.count()
            if count_before == 0:
                self.stdout.write("%s: sin compatibilidades, nada que limpiar." % product.sku)
                continue
            if dry_run:
                self.stdout.write(
                    "%s: se eliminarían %d compatibilidades y se crearía 1 con brand=%s, model=None."
                    % (product.sku, count_before, brand_obj.name)
                )
                continue
            with transaction.atomic():
                deleted, _ = product.compatibilities.all().delete()
                pc = ProductCompatibility.objects.create(
                    product=product,
                    brand=brand_obj,
                    model=None,
                    year_from=1900,
                    year_to=2100,
                    engine=None,
                    displacement_cc=None,
                    fuel_type=None,
                    notes="CLF backfill v2 compatibilidad amplia por marca",
                    confidence="BAJA",
                    is_active=True,
                )
            self.stdout.write(
                self.style.SUCCESS(
                    "%s: eliminadas %d compatibilidades; creada 1 amplia (id=%s, brand=%s, model=None)."
                    % (product.sku, deleted, pc.id, brand_obj.name)
                )
            )

    def _list_compatibilities(self, sku_brand_map):
        """Lista compatibilidades actuales para los SKUs del mapa."""
        products = list(
            Product.objects.filter(sku__in=sku_brand_map.keys()).select_related("category")
        )
        for product in products:
            self.stdout.write("%s  %s" % (product.sku, (product.name or "")[:60]))
            for pc in product.compatibilities.select_related("brand", "model").order_by("brand__name", "model__name"):
                model_str = pc.model.name if pc.model_id else "NULL (amplia)"
                self.stdout.write(
                    "  id=%s  brand=%s  model=%s  confidence=%s  notes=%s"
                    % (pc.id, pc.brand.name, model_str, pc.confidence, (pc.notes or "")[:50])
                )
            if not product.compatibilities.exists():
                self.stdout.write("  (sin compatibilidades)")
            self.stdout.write("")
