# -*- coding: utf-8 -*-
"""
Lista catalíticos Ensamble directo (CLF) y cantidad de ProductCompatibility.

La ficha pública ya arma el bloque "Aplicaciones registradas" desde la BD
(sin correr este comando). Útil para auditar qué SKUs tienen o no aplicaciones.

  python manage.py report_direct_fit_products
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductCompatibility

CLF_SLUGS = ("cataliticos-clf", "cataliticos-ensamble-directo")


class Command(BaseCommand):
    help = "Reporta productos Ensamble directo (CLF) y filas de compatibilidad."

    def handle(self, *args, **options):
        qs = (
            Product.objects.filter(
                category__slug__in=CLF_SLUGS,
                is_active=True,
                deleted_at__isnull=True,
            )
            .select_related("category")
            .order_by("sku")
        )
        self.stdout.write(f"Productos CLF / Ensamble directo: {qs.count()}\n")
        for p in qs:
            n = ProductCompatibility.objects.filter(product=p, is_active=True).count()
            flag = "OK" if n else "SIN COMPAT"
            self.stdout.write(f"  [{flag}] {p.sku}  {p.name[:50]}  compat={n}")
