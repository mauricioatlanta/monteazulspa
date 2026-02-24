"""
Compara SKUs del catálogo vs carpetas dentro de un ZIP de imágenes (ej. imagenes.zip).
Genera reporte CSV: missing_in_zip, extra_in_zip, matched.

Usa normalización canónica para matchear formatos distintos:
- DB: 1,75-X-10, 1.75X10, 2-X-6 ↔ ZIP: 175X10, 2X6, 25X6
"""
import csv
import os
import re
import zipfile

from django.core.management.base import BaseCommand

from apps.catalog.models import Product


def norm_key(s: str) -> str:
    """
    Clave canónica tipo ZIP:
    - 1,75 / 1.75 → 175
    - 2,5 / 2.5 → 25
    - quitar -, _, espacios
    - uppercase, solo letras y números
    """
    if not s:
        return ""
    s = s.strip().upper()
    # 1) unificar separadores decimales: 1,75 -> 1.75
    s = s.replace(",", ".")
    # 2) convertir decimales a formato sin punto: 1.75 -> 175, 2.5 -> 25, 10.7 -> 107
    s = re.sub(r"(\d+)\.(\d{1,2})", r"\1\2", s)
    # 3) eliminar todo lo que no sea letra o número
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def variants(s: str) -> set[str]:
    """Con esta normalización agresiva, casi no necesitas variantes."""
    k = norm_key(s)
    return {k}


class Command(BaseCommand):
    help = "Compara SKUs del catálogo vs carpetas dentro de un ZIP de imágenes y genera reporte CSV."

    def add_arguments(self, parser):
        parser.add_argument("--zip", required=True, help="Ruta al imagenes.zip")
        parser.add_argument(
            "--zip-root",
            default="imagenes/",
            help="Carpeta raíz dentro del zip (default: imagenes/)",
        )
        parser.add_argument(
            "--out",
            default="audit_images_report.csv",
            help="Salida CSV (default: audit_images_report.csv)",
        )
        parser.add_argument(
            "--field",
            default="sku",
            help="Campo del modelo Product a usar (sku o part_number)",
        )

    def handle(self, *args, **opts):
        zip_path = opts["zip"]
        zip_root = opts["zip_root"]
        out_path = opts["out"]
        field = opts["field"]

        if not os.path.exists(zip_path):
            self.stderr.write(self.style.ERROR(f"No existe: {zip_path}"))
            return

        # Normalizar zip_root para comparaciones (con / final)
        zip_root = zip_root.rstrip("/") + "/"

        # 1) Leer carpetas dentro del ZIP
        # Consideramos tanto entradas de directorio (imagenes/ABC123/) como rutas de archivos (imagenes/ABC123/file.png)
        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()

        folder_set = set()
        for n in names:
            if not n.startswith(zip_root):
                continue
            rel = n[len(zip_root) :].lstrip("/")
            if not rel:
                continue
            parts = rel.split("/")
            if parts[0]:
                folder_set.add(parts[0])

        zip_keys = set()
        zip_map = {}  # norm_key -> original folder name
        for f in folder_set:
            for v in variants(f):
                zip_keys.add(v)
                zip_map.setdefault(v, f)

        # 2) Leer SKUs desde DB
        if not hasattr(Product, field):
            self.stderr.write(self.style.ERROR(f"El modelo Product no tiene el campo '{field}'"))
            return

        qs = Product.objects.all().only("id", field)
        db_keys = set()
        db_rows = []
        for p in qs:
            val = getattr(p, field, "") or ""
            vset = variants(val)
            db_rows.append((p.id, val, vset))
            db_keys |= vset

        # 3) Comparar
        missing = []  # en DB, no en ZIP
        matched = []
        for pid, raw, vset in db_rows:
            hit = any(v in zip_keys for v in vset)
            if hit:
                matched.append((pid, raw))
            else:
                missing.append((pid, raw))

        extra = []  # en ZIP, no en DB
        for f in sorted(folder_set, key=lambda x: x.upper()):
            fvars = variants(f)
            if not any(v in db_keys for v in fvars):
                extra.append(f)

        # 4) Escribir CSV
        with open(out_path, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["section", "product_id", "db_value_or_folder"])
            for pid, raw in missing:
                w.writerow(["missing_in_zip", pid, raw])
            for pid, raw in matched:
                w.writerow(["matched", pid, raw])
            for f in extra:
                w.writerow(["extra_in_zip", "", f])

        self.stdout.write(self.style.SUCCESS("OK"))
        self.stdout.write(f"ZIP folders: {len(folder_set)}")
        self.stdout.write(f"Matched: {len(matched)} | Missing: {len(missing)} | Extra: {len(extra)}")
        self.stdout.write(f"Reporte: {out_path}")
