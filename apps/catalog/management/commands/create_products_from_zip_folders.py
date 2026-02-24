"""
Crea productos mínimos (draft) para carpetas del ZIP que no existen en el catálogo.
Usa la misma normalización que audit_zip_images para que "extra_in_zip" coincida.
Genera CSV: status, product_id, zip_folder, norm_key.
"""
import csv
import os
import re
import zipfile
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product


def norm_key(s: str) -> str:
    """Misma normalización que audit_zip_images para matchear DB vs ZIP."""
    if not s:
        return ""
    s = str(s).strip().upper()
    s = s.replace(",", ".")
    s = re.sub(r"(\d+)\.(\d{1,2})", r"\1\2", s)
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


class Command(BaseCommand):
    help = (
        "Crea productos mínimos (draft) para carpetas del ZIP que no existen en el catálogo. "
        "Genera CSV. Ejecutar sin --apply para solo listar; con --apply para crear."
    )

    def add_arguments(self, parser):
        parser.add_argument("--zip", required=True, help="Ruta al ZIP (ej. imagenes.zip)")
        parser.add_argument(
            "--zip-root",
            default="imagenes/",
            help="Carpeta raíz dentro del ZIP (default: imagenes/)",
        )
        parser.add_argument(
            "--field",
            default="sku",
            help="Campo del Product a comparar (default: sku)",
        )
        parser.add_argument(
            "--out",
            default="zip_missing_products.csv",
            help="Archivo CSV de salida (default: zip_missing_products.csv)",
        )
        parser.add_argument(
            "--category-slug",
            default="por-clasificar",
            help="Slug de categoría para productos nuevos (default: por-clasificar)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Crear productos en DB; sin esto solo genera el CSV con would_create",
        )

    def handle(self, *args, **opts):
        zip_path = opts["zip"]
        zip_root = opts["zip_root"].rstrip("/") + "/"
        field = opts["field"]
        out = opts["out"]
        category_slug = opts["category_slug"]
        apply_changes = opts["apply"]

        if not os.path.exists(zip_path):
            self.stderr.write(self.style.ERROR(f"No existe: {zip_path}"))
            return

        if not hasattr(Product, field):
            self.stderr.write(self.style.ERROR(f"El modelo Product no tiene el campo '{field}'"))
            return

        with zipfile.ZipFile(zip_path) as zf:
            names = zf.namelist()

        # Carpetas nivel 1 (misma lógica que audit_zip_images)
        folders = set()
        for n in names:
            if not n.startswith(zip_root):
                continue
            rel = n[len(zip_root) :].lstrip("/")
            if not rel:
                continue
            parts = rel.split("/")
            if parts[0]:
                folders.add(parts[0])

        # Catálogo existente por norm_key
        existing = {}
        for p in Product.objects.all().only("id", field):
            raw = getattr(p, field, "") or ""
            k = norm_key(raw)
            if k and k not in existing:
                existing[k] = p.id

        to_create = []
        for f in sorted(folders, key=lambda x: x.upper()):
            k = norm_key(f)
            if not k:
                continue
            if k in existing:
                continue
            to_create.append((f, k))

        # Categoría por defecto para productos nuevos
        category = None
        if apply_changes and to_create:
            category, _ = Category.objects.get_or_create(
                slug=category_slug,
                defaults={"name": "Por clasificar", "is_active": True},
            )

        created = 0
        rows = []

        for folder_name, k in to_create:
            rows.append(["would_create", "", folder_name, k])

            if apply_changes and category:
                slug_base = slugify(folder_name)[:280] or "producto"
                slug = slug_base
                cnt = 0
                while Product.objects.filter(slug=slug).exists():
                    cnt += 1
                    slug = f"{slug_base}-{cnt}"[:280]

                p = Product(
                    **{
                        field: folder_name,
                        "name": folder_name,
                        "slug": slug,
                        "category": category,
                        "price": Decimal("0"),
                        "cost_price": Decimal("0"),
                        "is_active": False,
                        "stock": 0,
                    }
                )
                p.save()
                created += 1
                rows[-1] = ["created", p.id, folder_name, k]

        with open(out, "w", newline="", encoding="utf-8") as fp:
            w = csv.writer(fp)
            w.writerow(["status", "product_id", "zip_folder", "norm_key"])
            w.writerows(rows)

        self.stdout.write(self.style.SUCCESS("OK"))
        self.stdout.write(f"ZIP folders: {len(folders)}")
        self.stdout.write(f"Missing products (from ZIP): {len(to_create)}")
        self.stdout.write(f"Created (--apply): {created}")
        self.stdout.write(f"Reporte: {out}")
