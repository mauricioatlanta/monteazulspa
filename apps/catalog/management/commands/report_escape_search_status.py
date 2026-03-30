# -*- coding: utf-8 -*-
"""
Reporte de estado técnico del catálogo de escapes.
Usa exclusivamente apps.catalog.escape_search_utils para clasificación.
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.catalog.escape_search_utils import (
    get_products_queryset,
    is_direct_fit_product,
    is_ready_for_escape_search,
    is_incomplete_for_escape_search,
)


class Command(BaseCommand):
    help = "Genera reporte de estado técnico del catálogo de escapes (por tipo: flexibles exigen largo_mm)"

    def handle(self, *args, **options):

        base = Path("tmp")
        base.mkdir(exist_ok=True)

        ready_file = base / "productos_listos_busqueda_escape.csv"
        incomplete_file = base / "productos_incompletos_escape.csv"
        directfit_file = base / "productos_direct_fit_escape.csv"

        ready = []
        incomplete = []
        directfit = []

        qs = get_products_queryset()

        for p in qs:
            if is_direct_fit_product(p):
                directfit.append(p)
            elif is_ready_for_escape_search(p):
                ready.append(p)
            elif is_incomplete_for_escape_search(p):
                incomplete.append(p)

        # Guardar CSV READY
        with open(ready_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["SKU", "Nombre", "Entrada", "Salida", "Largo_mm"])
            for p in ready:
                w.writerow([
                    p.sku,
                    p.name,
                    p.diametro_entrada,
                    p.diametro_salida,
                    p.largo_mm
                ])

        # Guardar CSV INCOMPLETE
        with open(incomplete_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["SKU", "Nombre"])
            for p in incomplete:
                w.writerow([p.sku, p.name])

        # Guardar CSV DIRECT FIT
        with open(directfit_file, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["SKU", "Nombre"])
            for p in directfit:
                w.writerow([p.sku, p.name])

        self.stdout.write("")
        self.stdout.write("===== REPORTE BUSQUEDA ESCAPE =====")
        self.stdout.write(f"Listos: {len(ready)}")
        self.stdout.write(f"Incompletos: {len(incomplete)}")
        self.stdout.write(f"Direct Fit: {len(directfit)}")
        self.stdout.write("")
        self.stdout.write(f"CSV READY: {ready_file}")
        self.stdout.write(f"CSV INCOMPLETE: {incomplete_file}")
        self.stdout.write(f"CSV DIRECT FIT: {directfit_file}")
