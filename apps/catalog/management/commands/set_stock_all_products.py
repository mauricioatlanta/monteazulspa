# -*- coding: utf-8 -*-
"""
Establece el stock de todos los productos a una cantidad fija.
Uso: python manage.py set_stock_all_products [cantidad]
Por defecto 50. Ejemplo: python manage.py set_stock_all_products 50
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Establece el stock de todos los productos a una cantidad fija (por defecto 50)."

    def add_arguments(self, parser):
        parser.add_argument(
            "cantidad",
            nargs="?",
            type=int,
            default=50,
            help="Unidades de stock a asignar a cada producto (default: 50)",
        )

    def handle(self, *args, **options):
        cantidad = options["cantidad"]
        if cantidad < 0:
            self.stderr.write(self.style.ERROR("La cantidad debe ser >= 0."))
            return

        total = Product.objects.update(stock=cantidad)
        self.stdout.write(
            self.style.SUCCESS(f"Stock establecido a {cantidad} unidades en {total} producto(s).")
        )
