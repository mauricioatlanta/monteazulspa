# -*- coding: utf-8 -*-
"""
Importa diámetros y largos desde planilla Excel del proveedor.

- Hoja SILENCIADORES: detecta fila con PART# e INLET/OUTLET como header, luego PART#, INLET/OUTLET, BODY, OVERALL, PRICE.
- Hoja FLEXIBLES: medidas tipo 1,75 x 4; busca por categoría flexible y medida.
- Hoja COLAS DE ESCAPE: fija 2" entrada/salida.
- Omite Ensamble Directo (CLF).

Uso:
  python manage.py import_muffler_specs_from_excel --file tmp/lista_precios.xlsx --dry-run
  python manage.py import_muffler_specs_from_excel --file tmp/lista_precios.xlsx
"""
from decimal import Decimal
import re
from pathlib import Path

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import Category, Product

# Categorías donde están los flexibles en la BD
FLEX_CATEGORY_SLUGS = ["flexibles-normales", "flexibles-con-extension"]

# INLET/OUTLET: 2"-2" Offset-Center, 2.5"-2.5" Dual-Dual
PATTERN_INLET_OUTLET = re.compile(
    r'(\d+(?:[.,]\d+)?)"\s*-\s*(\d+(?:[.,]\d+)?)"',
    re.IGNORECASE
)

# Flexibles: 1,75 x 4, 2-X10, 3-X-6, 2 X 8
PATTERN_FLEX_MEASURE = re.compile(
    r'^\s*(\d+(?:[.,]\d+)?)\s*[-]?\s*[xX]\s*[-]?\s*(\d+(?:[.,]\d+)?)\s*$',
    re.IGNORECASE
)


def _canonical_num_for_key(value):
    """Formato canónico de número para clave: 2.0 -> 2, 1.75 -> 1.75."""
    n = float(value)
    return str(int(n)) if n == int(n) else str(n).rstrip("0").rstrip(".")


def _normalize_flexible_key(value):
    """
    Normaliza texto de medida/SKU a clave comparable.
    Ejemplos: 1,75 x 10 -> 1.75X10; 2-X10 -> 2X10; 3-X-6 -> 3X6.
    """
    s = str(value or "").strip().upper()
    s = s.replace(",", ".")
    s = s.replace('"', "")
    s = s.replace(" ", "")
    s = s.replace("-X-", "X")
    s = s.replace("-X", "X")
    s = s.replace("X-", "X")
    s = s.replace("-", "")
    return s


def _norm_sheet_name(name):
    return re.sub(r'\s+', ' ', (name or '').strip()).lower()


def parse_inlet_outlet(text):
    """Extrae (diam_entrada, diam_salida) de INLET/OUTLET. Acepta coma o punto decimal."""
    if text is None or (isinstance(text, str) and not str(text).strip()):
        return None, None
    s = str(text).strip()
    m = PATTERN_INLET_OUTLET.search(s)
    if not m:
        return None, None
    try:
        d1 = float(m.group(1).replace(',', '.'))
        d2 = float(m.group(2).replace(',', '.'))
        return d1, d2
    except (ValueError, TypeError):
        return None, None


def parse_flexible_measure(text):
    """
    Parsea medida flexible: '1,75 x 4', '2-X10', '3-X-6', '2 X 8'.
    Devuelve (diam, largo_pulg) o (None, None).
    """
    if text is None or (isinstance(text, str) and not str(text).strip()):
        return None, None
    s = str(text).strip().replace(",", ".")
    m = PATTERN_FLEX_MEASURE.match(s)
    if not m:
        return None, None
    try:
        diam = float(m.group(1))
        largo = float(m.group(2))
        if diam <= 0 or largo <= 0:
            return None, None
        return diam, largo
    except (ValueError, TypeError):
        return None, None


def _to_number(val):
    """Convierte valor de celda a número (para BODY, OVERALL)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val == val else None  # skip NaN
    s = str(val).strip().replace(',', '.')
    s = re.sub(r'[^\d.-]', '', s)
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


class Command(BaseCommand):

    help = (
        "Importa diámetros y largos desde Excel: SILENCIADORES, FLEXIBLES, COLAS DE ESCAPE. "
        "Omite Ensamble Directo (CLF)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Ruta al Excel del proveedor (ej. tmp/lista_precios.xlsx)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se actualizaría, sin guardar.",
        )

    def handle(self, *args, **options):
        file_path = options["file"]
        dry_run = options["dry_run"]

        path = Path(file_path)
        if not path.is_absolute():
            path = Path(settings.BASE_DIR) / file_path
        path = path.resolve()

        if not path.exists():
            raise CommandError(
                f"Archivo no encontrado: {path}\n"
                "Crea la carpeta (ej. mkdir -p tmp), sube la planilla y vuelve a ejecutar con --file tmp/lista_precios.xlsx"
            )

        self.stdout.write(f"Leyendo: {path}")

        stats = {
            "silenciadores": 0,
            "flexibles": 0,
            "colas": 0,
            "no_encontrados": 0,
            "errores_parseo": 0,
            "flexibles_encontrados": 0,
            "flexibles_no_encontrados": 0,
            "flexibles_ambiguos": 0,
            "errores_parseo_flexibles": 0,
        }

        xl = pd.ExcelFile(str(path))
        sheet_names = {_norm_sheet_name(s): s for s in xl.sheet_names}

        # ---------- A. Hoja SILENCIADORES ----------
        sil_key = "silenciadores"
        if sil_key in sheet_names:
            df_sil = pd.read_excel(xl, sheet_name=sheet_names[sil_key], header=None)

            # Buscar la fila que contiene PART# e INLET/OUTLET
            header_idx = None
            for idx, row in df_sil.iterrows():
                values = [str(v).strip() for v in row.tolist()]
                if "PART#" in values and "INLET/OUTLET" in values:
                    header_idx = idx
                    break

            if header_idx is None:
                raise CommandError(
                    "No se encontró fila de encabezado válida en hoja SILENCIADORES "
                    "(debe contener PART# e INLET/OUTLET)."
                )

            # Promover esa fila a header y tomar solo datos debajo
            df_sil.columns = [str(v).strip() for v in df_sil.iloc[header_idx].tolist()]
            df_sil = df_sil.iloc[header_idx + 1 :].copy()
            df_sil = df_sil.reset_index(drop=True)
            df_sil.columns = [str(c).strip() for c in df_sil.columns]

            for _, row in df_sil.iterrows():
                sku = str(row.get("PART#", "")).strip()
                if not sku or sku.lower() == "nan":
                    continue

                inlet_outlet = str(row.get("INLET/OUTLET", "")).strip()
                body_num = _to_number(row.get("BODY"))
                overall_num = _to_number(row.get("OVERALL"))

                diam_in, diam_out = parse_inlet_outlet(inlet_outlet)
                if diam_in is None:
                    stats["errores_parseo"] += 1
                    continue

                try:
                    product = Product.objects.get(sku=sku)
                except Product.DoesNotExist:
                    stats["no_encontrados"] += 1
                    continue

                if product.category and "directo" in (product.category.name or "").lower():
                    continue

                # Solo rellenar si aún no tiene diámetro (evitar sobrescribir)
                if product.diametro_entrada is not None and not dry_run:
                    continue

                if dry_run:
                    self.stdout.write(
                        f"[DRY-RUN] {sku} -> entrada={diam_in} salida={diam_out} cuerpo={body_num} total={overall_num}"
                    )
                else:
                    product.diametro_entrada = Decimal(str(round(diam_in, 2)))
                    product.diametro_salida = Decimal(str(round(diam_out, 2)))
                    update_fields = ["diametro_entrada", "diametro_salida"]
                    if overall_num is not None and overall_num > 0:
                        # Si parece pulgadas (< 100), convertir a mm
                        largo_mm = int(overall_num * 25.4) if overall_num < 100 else int(overall_num)
                        product.largo_mm = largo_mm
                        update_fields.append("largo_mm")
                    product.save(update_fields=update_fields)
                stats["silenciadores"] += 1

        # ---------- B. Hoja FLEXIBLES ----------
        flex_key = "flexibles"
        if flex_key in sheet_names:
            categories_flex = Category.objects.filter(slug__in=FLEX_CATEGORY_SLUGS)
            products_flex = Product.objects.filter(category__in=categories_flex) if categories_flex.exists() else Product.objects.none()

            df_flex = pd.read_excel(xl, sheet_name=sheet_names[flex_key], header=None)
            seen_excel_keys = set()

            for idx, row in df_flex.iterrows():
                if idx < 1:
                    continue
                row_str = " ".join(str(c) for c in row if pd.notna(c))
                if "FLEXIBLES REFORZADOS" in row_str.upper():
                    continue
                for cell in row:
                    if pd.isna(cell):
                        continue
                    measure_str = str(cell).strip()
                    if not measure_str or measure_str.lower() == "nan":
                        continue

                    diam, largo_pulg = parse_flexible_measure(measure_str)
                    if diam is None:
                        stats["errores_parseo_flexibles"] += 1
                        continue

                    # Clave canónica: 2X8, 1.75X6, 2.5X8 (solo parse error cuenta en errores_parseo_flexibles)
                    excel_key = f"{_canonical_num_for_key(diam)}X{_canonical_num_for_key(largo_pulg)}"
                    if not excel_key or excel_key in seen_excel_keys:
                        continue
                    seen_excel_keys.add(excel_key)

                    def sku_norm(p):
                        return _normalize_flexible_key(p.sku)

                    def name_norm(p):
                        return _normalize_flexible_key(p.name or "")

                    # Candidatos: SKU o nombre normalizado coincide con clave canónica
                    excel_key_norm = _normalize_flexible_key(excel_key)
                    candidates = [p for p in products_flex if sku_norm(p) == excel_key_norm or excel_key_norm in name_norm(p)]
                    if not candidates:
                        stats["flexibles_no_encontrados"] += 1
                        if dry_run:
                            self.stdout.write(f"[NO_MATCH][FLEXIBLE] {measure_str} -> key={excel_key}")
                        continue

                    # Orden de prioridad: 1) sku exacto == clave canónica 2) sin EXT 3) nombre "Flexible Reforzado" 4) flexibles-normales 5) flexibles-con-extension
                    def sort_key(p):
                        sku_upper = (p.sku or "").strip().upper()
                        has_ext = "EXT" in sku_upper
                        name_ok = (p.name or "").strip().startswith("Flexible Reforzado")
                        cat_normales = p.category.slug == "flexibles-normales"
                        return (
                            0 if sku_upper == excel_key.upper() else 1,
                            0 if not has_ext else 1,
                            0 if name_ok else 1,
                            0 if cat_normales else 1,
                            (p.sku or "").upper(),
                        )

                    candidates.sort(key=sort_key)
                    product = candidates[0]
                    if len(candidates) > 1:
                        stats["flexibles_ambiguos"] += 1
                        if dry_run:
                            candidatos_str = [p.sku for p in candidates]
                            self.stdout.write(
                                self.style.WARNING(
                                    f"[AMBIGUO][FLEXIBLE] {measure_str} -> key={excel_key} candidatos={candidatos_str}"
                                )
                            )

                    largo_mm = int(round(largo_pulg * 25.4))
                    if dry_run:
                        self.stdout.write(
                            f"[DRY-RUN] Flexible {measure_str} -> sku={product.sku} entrada={diam} salida={diam} largo={int(largo_pulg) if largo_pulg == int(largo_pulg) else largo_pulg}"
                        )
                    else:
                        product.diametro_entrada = Decimal(str(round(diam, 2)))
                        product.diametro_salida = Decimal(str(round(diam, 2)))
                        product.largo_mm = largo_mm
                        product.save(update_fields=["diametro_entrada", "diametro_salida", "largo_mm"])
                    stats["flexibles_encontrados"] += 1
                    stats["flexibles"] += 1

        # ---------- C. Hoja COLAS DE ESCAPE ----------
        processed_skus = set()
        colas_key = "colas de escape"
        if colas_key in sheet_names:
            df_colas = pd.read_excel(xl, sheet_name=sheet_names[colas_key], header=None)
            for idx, row in df_colas.iterrows():
                if idx < 1:
                    continue
                code = row.iloc[0] if len(row) else None
                if pd.isna(code) or not str(code).strip():
                    continue
                sku = str(code).strip().upper().replace(",", ".").replace(" ", "-")[:50]
                if not sku or sku.lower() == "nan" or sku in ("COLAS", "CODIGO", "VALOR", "FLEXIBLES"):
                    continue
                if sku in processed_skus:
                    continue
                try:
                    product = Product.objects.get(sku=sku)
                except Product.DoesNotExist:
                    product = Product.objects.filter(sku__iexact=sku).first()
                if not product:
                    continue
                # Solo rellenar si aún no tiene diámetro
                if product.diametro_entrada is not None and not dry_run:
                    continue
                processed_skus.add(product.sku.upper())
                if dry_run:
                    self.stdout.write(f"[DRY-RUN] {product.sku} -> entrada=2.0 salida=2.0")
                else:
                    product.diametro_entrada = Decimal("2.0")
                    product.diametro_salida = Decimal("2.0")
                    product.save(update_fields=["diametro_entrada", "diametro_salida"])
                stats["colas"] += 1

        # Colas por prefijo GW que sigan sin diámetro (sin duplicar con processed_skus)
        colas_gw = Product.objects.filter(
            sku__startswith="GW",
            diametro_entrada__isnull=True,
        )
        for product in colas_gw:
            if product.sku.upper() in processed_skus:
                continue
            processed_skus.add(product.sku.upper())
            if dry_run:
                self.stdout.write(f"[DRY-RUN] {product.sku} -> entrada=2.0 salida=2.0")
            else:
                product.diametro_entrada = Decimal("2.0")
                product.diametro_salida = Decimal("2.0")
                product.save(update_fields=["diametro_entrada", "diametro_salida"])
            stats["colas"] += 1

        # ---------- Salida ----------
        self.stdout.write(
            f"Silenciadores: {stats['silenciadores']} | "
            f"Colas: {stats['colas']} | "
            f"No encontrados: {stats['no_encontrados']} | "
            f"Errores parseo: {stats['errores_parseo']}"
        )
        self.stdout.write(
            f"Flexibles encontrados: {stats['flexibles_encontrados']} | "
            f"Flexibles no encontrados: {stats['flexibles_no_encontrados']} | "
            f"Flexibles ambiguos: {stats['flexibles_ambiguos']} | "
            f"Errores parseo flexibles: {stats['errores_parseo_flexibles']}"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardaron cambios."))
