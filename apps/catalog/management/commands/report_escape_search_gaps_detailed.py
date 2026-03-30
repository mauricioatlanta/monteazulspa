# -*- coding: utf-8 -*-
"""
Reporte detallado de productos incompletos para búsqueda por medidas.

Desglosa los productos que NO están listos para el buscador técnico por:
- sin diámetro de entrada
- sin diámetro de salida
- sin largo (relevante en flexibles)
- rescatables desde SKU (fill_escape_search_fields)

Usa exclusivamente apps.catalog.escape_search_utils para clasificación.
No importa desde .report_escape_search_status.

Uso:
  python manage.py report_escape_search_gaps_detailed
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand

from apps.catalog.flexibles_nomenclature import parse_flexible_measure_from_sku
from apps.catalog.escape_search_utils import (
    get_products_queryset,
    is_flexible_product,
    is_incomplete_for_escape_search,
)


class Command(BaseCommand):
    help = "Desglosa productos incompletos por motivo (falta entrada/salida/largo) y marca rescatables desde SKU"

    def handle(self, *args, **options):
        base = Path("tmp")
        base.mkdir(exist_ok=True)
        out_file = base / "productos_incompletos_escape_detalle.csv"

        qs = get_products_queryset()
        incompletos = [p for p in qs if is_incomplete_for_escape_search(p)]

        # Desglose por motivo y rescatables
        rows = []
        sin_entrada = 0
        sin_salida = 0
        sin_largo = 0
        sin_ambos_diam = 0
        solo_texto = 0
        rescatable_sku = 0

        for p in incompletos:
            falta_entrada = not (p.diametro_entrada is not None and p.diametro_entrada != 0)
            falta_salida = not (p.diametro_salida is not None and p.diametro_salida != 0)
            falta_largo = not (p.largo_mm is not None and p.largo_mm != 0)

            if falta_entrada:
                sin_entrada += 1
            if falta_salida:
                sin_salida += 1
            if is_flexible_product(p) and falta_largo:
                sin_largo += 1
            if falta_entrada and falta_salida:
                sin_ambos_diam += 1
            if falta_entrada and falta_salida and (not is_flexible_product(p) or falta_largo):
                solo_texto += 1

            parsed = parse_flexible_measure_from_sku(p.sku)
            rescate = bool(parsed) and (falta_entrada or falta_salida or (is_flexible_product(p) and falta_largo))
            if rescate:
                rescatable_sku += 1

            cat_slug = p.category.slug if p.category_id else ""
            notas = []
            if falta_entrada:
                notas.append("falta entrada")
            if falta_salida:
                notas.append("falta salida")
            if is_flexible_product(p) and falta_largo:
                notas.append("falta largo")
            if rescate:
                notas.append("rescatable con fill_escape_search_fields")

            rows.append({
                "sku": p.sku or "",
                "nombre": (p.name or "")[:200],
                "categoria": cat_slug,
                "falta_entrada": "Sí" if falta_entrada else "",
                "falta_salida": "Sí" if falta_salida else "",
                "falta_largo": "Sí" if (is_flexible_product(p) and falta_largo) else "",
                "rescatable_desde_sku": "Sí" if rescate else "",
                "notas": "; ".join(notas),
            })

        rows.sort(key=lambda r: (r["rescatable_desde_sku"] != "Sí", r["categoria"], r["sku"]))

        with open(out_file, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "sku", "nombre", "categoria",
                    "falta_entrada", "falta_salida", "falta_largo",
                    "rescatable_desde_sku", "notas",
                ],
            )
            w.writeheader()
            w.writerows(rows)

        self.stdout.write("")
        self.stdout.write("===== REPORTE GAPS DETALLADO (incompletos) =====")
        self.stdout.write(f"Total incompletos: {len(incompletos)}")
        self.stdout.write(f"Sin diámetro entrada: {sin_entrada}")
        self.stdout.write(f"Sin diámetro salida: {sin_salida}")
        self.stdout.write(f"Sin largo (flexibles): {sin_largo}")
        self.stdout.write(f"Sin ambos diámetros: {sin_ambos_diam}")
        self.stdout.write(f"Rescatables desde SKU (fill_escape_search_fields): {rescatable_sku}")
        self.stdout.write("")
        self.stdout.write(f"CSV: {out_file}")
