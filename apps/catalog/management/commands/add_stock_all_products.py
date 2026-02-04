# -*- coding: utf-8 -*-
"""
Suma una cantidad fija al stock de todos los productos.
Uso: python manage.py add_stock_all_products [cantidad]
Por defecto suma 500. Ejemplo: python manage.py add_stock_all_products 500
"""
from django.db.models import F
from django.core.management.base import BaseCommand

from apps.catalog.models import Product


class Command(BaseCommand):
    help = "Suma una cantidad al stock de todos los productos (por defecto 500)."

    def add_arguments(self, parser):
        parser.add_argument(
            "cantidad",
            nargs="?",
            type=int,
            default=500,
            help="Unidades a sumar al stock de cada producto (default: 500)",
        )

    def handle(self, *args, **options):
        cantidad = options["cantidad"]
        if cantidad < 0:
            self.stderr.write(self.style.ERROR("La cantidad debe ser >= 0."))
            return

        total = Product.objects.update(stock=F("stock") + cantidad)
        self.stdout.write(
            self.style.SUCCESS(f"Se sumaron {cantidad} unidades al stock de {total} producto(s).")
        )
