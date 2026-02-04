# -*- coding: utf-8 -*-
"""
Carga productos desde lista precios publico.xlsx al catálogo.
Una hoja = una categoría. Productos ordenados por categoría.
Uso: python manage.py load_precios_xlsx "ruta/al/archivo.xlsx"

Requisito: pip install openpyxl  (o: pip install -r requirements-catalog.txt)
"""
import re
from decimal import Decimal
from pathlib import Path

import openpyxl
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product


def _normalize_category_name(sheet_name):
    """Limpia nombre de hoja para usarlo como categoría."""
    name = (sheet_name or "").strip()
    name = re.sub(r"\s+", " ", name)
    return name.title() if name else "Sin categoría"


def _to_decimal(val):
    if val is None:
        return Decimal("0")
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    s = str(val).strip().replace(",", ".")
    try:
        return Decimal(re.sub(r"[^\d.-]", "", s) or "0")
    except Exception:
        return Decimal("0")


# Nombres de columna que no deben importarse como SKU
_HEADER_SKUS = frozenset({"CODIGO", "VALOR", "PART#", "PRICE", "INLET/OUTLET", "CONFIGURE", "BODY", "OVERALL", "MATERIAL", "PHOTO", "MEDIDA", "MODELO", "PULGADAS", "PRECIO", "FLEXIBLES", "COLAS", "REFORZADOS", "EURO", "IVA", "INCLUIDO"})


def _to_sku(val):
    """
    Genera SKU (part number) a partir del valor.
    Para flexibles la medida es el part number: coma decimal → punto (ej. 2,5 X 6 → 2.5X6).
    """
    if val is None:
        return ""
    s = str(val).strip().upper()
    s = s.replace(",", ".")  # coma → punto (medida/part number)
    s = re.sub(r"\s*[xX]\s*", "X", s)  # "2.5 X 6" → "2.5X6"
    s = re.sub(r"\s+", "-", s)[:50]
    if s in _HEADER_SKUS:
        return ""
    return s if s else ""


def _build_product_name(row, code_col, name_cols):
    """Construye nombre del producto desde código y columnas extra."""
    code = (row[code_col] or "").strip() if code_col is not None else ""
    parts = [code] if code else []
    for idx in name_cols:
        if idx is not None and idx < len(row) and row[idx]:
            v = str(row[idx]).strip()
            if v and v not in parts:
                parts.append(v)
    return " ".join(parts)[:255] if parts else (code or "Sin nombre")


def _find_header_row(rows, keywords):
    """Encuentra la fila que contiene alguna de las palabras clave (para código/precio)."""
    for i, row in enumerate(rows):
        row_str = " ".join(str(c).upper() for c in row if c)
        if any(k in row_str for k in keywords):
            return i
    return -1


def _parse_sheet(ws):
    """
    Parsea una hoja y devuelve (category_name, list of (sku, name, price)).
    Adaptado a las estructuras observadas: SILENCIADORES (10 cols), FLEXIBLES/COLAS (2),
    CATALITICOS CLF/TIPO ORIGINAL (3), CATALITICOS TWC (4).
    """
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return ws.title, []

    category_name = _normalize_category_name(ws.title)
    data = []

    # Detectar estructura por número de columnas y contenido
    ncols = max(len(r) for r in rows) if rows else 0

    if ncols >= 10:
        # SILENCIADORES: PART# col 0, PRICE col 8, nombre desde varias columnas
        header_idx = _find_header_row(rows[:10], ["PART#", "PRICE"])
        if header_idx < 0:
            header_idx = 3
        start = header_idx + 1
        for row in rows[start:]:
            row = list(row) if row else []
            if len(row) < 9:
                continue
            sku = _to_sku(row[0])
            price = _to_decimal(row[8])
            if not sku or price <= 0:
                continue
            name = _build_product_name(row, 0, [1, 2, 3])
            data.append((sku, name, price))

    elif ncols >= 4:
        # CATALITICOS TWC: codigo, modelo, pulgadas, precio
        header_idx = _find_header_row(rows[:5], ["codigo", "CODIGO", "precio", "PRECIO"])
        if header_idx < 0:
            header_idx = 1
        start = header_idx + 1
        for row in rows[start:]:
            row = list(row) if row else []
            if len(row) < 4:
                continue
            sku = _to_sku(row[0])
            price = _to_decimal(row[3])
            if not sku or price <= 0:
                continue
            name = _build_product_name(row, 0, [1, 2])
            data.append((sku, name, price))

    elif ncols >= 3:
        # CATALITICOS CLF o TIPO ORIGINAL: code, ?, price
        header_idx = _find_header_row(rows[:5], ["VALOR", "MEDIDA", "codigo", "CODIGO", "EURO"])
        if header_idx < 0:
            header_idx = 1
        start = header_idx + 1
        for row in rows[start:]:
            row = list(row) if row else []
            if len(row) < 3:
                continue
            sku = _to_sku(row[0])
            price = _to_decimal(row[2])
            if not sku or price <= 0:
                continue
            name = _build_product_name(row, 0, [1])
            data.append((sku, name, price))

    else:
        # 2 columnas: FLEXIBLES, COLAS DE ESCAPE
        header_idx = _find_header_row(rows[:6], ["VALOR", "CODIGO", "FLEXIBLES", "COLAS"])
        if header_idx < 0:
            header_idx = 2
        start = header_idx + 1
        for row in rows[start:]:
            row = list(row) if row else []
            if len(row) < 2:
                continue
            code = (row[0] or "").strip()
            price = _to_decimal(row[1])
            if not code or price <= 0:
                continue
            sku = _to_sku(code)
            if not sku:
                code_normalized = code.replace(",", ".")
                sku = slugify(code_normalized).replace("-", "")[:50].upper() or "ITEM"
            name = str(code).replace(",", ".")[:255]
            data.append((sku, name, price))

    return category_name, data


class Command(BaseCommand):
    help = "Carga productos desde lista precios publico.xlsx (por categoría)."

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            type=str,
            help="Ruta al archivo .xlsx (ej: /home/usuario/lista precios publico.xlsx)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se importaría, sin guardar.",
        )

    def handle(self, path, dry_run, **options):
        path = Path(path).resolve()
        if not path.exists():
            self.stderr.write(self.style.ERROR(f"Archivo no encontrado: {path}"))
            self.stderr.write(
                "Indica la ruta real al .xlsx en este servidor (ej: /home/usuario/lista precios publico.xlsx)"
            )
            return

        self.stdout.write(f"Leyendo {path} ...")
        wb = openpyxl.load_workbook(path, read_only=True)

        created_cats = 0
        created_prods = 0
        updated_prods = 0

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            category_name, items = _parse_sheet(ws)
            if not items:
                self.stdout.write(f"  {sheet_name}: sin filas de datos, omitido.")
                continue

            if dry_run:
                self.stdout.write(f"  [{category_name}] {len(items)} productos")
                for sku, name, price in items[:3]:
                    self.stdout.write(f"    - {sku} | {name[:40]}... | {price}")
                if len(items) > 3:
                    self.stdout.write(f"    ... y {len(items) - 3} más")
                continue

            cat, created = Category.objects.get_or_create(
                name=category_name,
                defaults={
                    "slug": slugify(category_name),
                    "is_active": True,
                    "parent": None,  # categoría raíz para el filtro del catálogo
                },
            )
            if created:
                created_cats += 1

            for sku, name, price in items:
                if not sku:
                    continue
                slug_base = slugify(sku)[:280]
                slug = slug_base
                cnt = 0
                while Product.objects.filter(slug=slug).exists():
                    cnt += 1
                    slug = f"{slug_base}-{cnt}"[:280]

                prod, created = Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        "name": name or sku,
                        "slug": slug,
                        "category": cat,
                        "price": price,
                        "cost_price": Decimal("0"),
                        "stock": 0,
                        "is_active": True,
                        "deleted_at": None,
                    },
                )
                if created:
                    created_prods += 1
                else:
                    updated_prods += 1
                prod.refresh_quality(save=True)

        wb.close()

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry-run listo. Ejecuta sin --dry-run para importar."))
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {created_cats} categorías nuevas, {created_prods} productos nuevos, {updated_prods} actualizados."
            )
        )
