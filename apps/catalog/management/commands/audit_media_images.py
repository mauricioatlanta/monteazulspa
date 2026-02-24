"""
Auditoría de imágenes de productos: existencia en disco, productos sin imagen, duplicados por hash.
Exporta reporte CSV + JSON en BASE_DIR/reports/ (o directorio indicado).
"""
import csv
import hashlib
import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage

from apps.catalog.models import Product, ProductImage


def _file_hash(path: Path, chunk_size: int = 8192) -> str:
    """Calcula SHA256 de un archivo."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _collect_media_hashes(media_root: Path, subdir: str = "products") -> dict:
    """
    Recorre media_root/subdir y devuelve { hash: [list of relative paths] }.
    Solo incluye hashes con más de un archivo (duplicados).
    """
    by_hash = {}
    base = media_root / subdir
    if not base.exists():
        return {}
    for root, _dirs, files in os.walk(base):
        for name in files:
            path = Path(root) / name
            try:
                digest = _file_hash(path)
                rel = path.relative_to(media_root)
                by_hash.setdefault(digest, []).append(str(rel).replace("\\", "/"))
            except (OSError, ValueError):
                continue
    return {h: paths for h, paths in by_hash.items() if len(paths) > 1}


class Command(BaseCommand):
    help = "Audita ProductImage: existencia en disco, productos sin imagen, duplicados por hash. Exporta CSV y JSON."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reports-dir",
            type=str,
            default=None,
            help="Directorio de salida para reportes (default: BASE_DIR/reports)",
        )
        parser.add_argument(
            "--no-hash",
            action="store_true",
            help="No calcular duplicados por hash (más rápido)",
        )

    def handle(self, *args, **options):
        reports_dir = options.get("reports_dir")
        if not reports_dir:
            reports_dir = Path(settings.BASE_DIR) / "reports"
        else:
            reports_dir = Path(reports_dir)
        reports_dir.mkdir(parents=True, exist_ok=True)

        no_hash = options.get("no_hash", False)
        storage = default_storage
        media_root = Path(settings.MEDIA_ROOT)

        # 1) Revisar cada ProductImage
        rows = []
        missing_count = 0
        products_without_image = set()

        products_total = Product.objects.filter(is_active=True, deleted_at__isnull=True).count()
        images = (
            ProductImage.objects.all()
            .select_related("product")
            .order_by("product_id", "position", "id")
        )
        images_list = list(images)
        total_images = len(images_list)

        for img in images_list:
            db_path = img.image.name if img.image else ""
            exists = bool(db_path and storage.exists(db_path))
            if not exists:
                missing_count += 1
                products_without_image.add(img.product_id)

            # Candidatos encontrados por basename (para notas)
            found_candidates = []
            if not exists and db_path and media_root:
                basename = os.path.basename(db_path)
                if basename:
                    for root, _dirs, files in os.walk(media_root):
                        for f in files:
                            if f.lower() == basename.lower():
                                rel = os.path.relpath(os.path.join(root, f), media_root)
                                found_candidates.append(rel.replace("\\", "/"))

            notes = []
            if not exists and found_candidates:
                notes.append(f"candidates:{','.join(found_candidates[:3])}")
            elif not exists:
                notes.append("missing")

            rows.append({
                "product_id": img.product_id,
                "sku": img.product.sku if img.product_id else "",
                "product_name": (img.product.name or "")[:100] if img.product_id else "",
                "image_id": img.pk,
                "db_path": db_path,
                "exists": exists,
                "found_candidates": found_candidates[:5],
                "notes": "; ".join(notes) if notes else "",
            })

        # Productos sin ninguna imagen
        product_ids_with_images = {r["product_id"] for r in rows}
        all_product_ids = set(
            Product.objects.filter(is_active=True, deleted_at__isnull=True).values_list("id", flat=True)
        )
        products_no_image = all_product_ids - product_ids_with_images
        for pid in products_no_image:
            p = Product.objects.filter(pk=pid).first()
            rows.append({
                "product_id": pid,
                "sku": p.sku if p else "",
                "product_name": (p.name or "")[:100] if p else "",
                "image_id": "",
                "db_path": "",
                "exists": False,
                "found_candidates": [],
                "notes": "product_without_image",
            })

        # 2) Duplicados por hash (solo en media/products/)
        duplicates_by_hash = {}
        if not no_hash and media_root.exists():
            duplicates_by_hash = _collect_media_hashes(media_root, "products")

        # Resumen
        summary = {
            "total_products": products_total,
            "total_product_images": total_images,
            "missing_files": missing_count,
            "products_without_any_image": len(products_no_image),
            "products_with_missing_image": len(products_without_image),
            "duplicate_groups_by_hash": len(duplicates_by_hash),
            "duplicate_files_count": sum(len(v) for v in duplicates_by_hash.values()),
        }

        # Export CSV
        csv_path = reports_dir / "audit_media_images.csv"
        fieldnames = ["product_id", "sku", "product_name", "image_id", "db_path", "exists", "found_candidates", "notes"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                r2 = dict(r)
                r2["found_candidates"] = "|".join(r2.get("found_candidates") or [])
                w.writerow(r2)
        self.stdout.write(self.style.SUCCESS(f"CSV: {csv_path}"))

        # Export JSON
        json_path = reports_dir / "audit_media_images.json"
        payload = {
            "summary": summary,
            "rows": rows,
            "duplicates_by_hash": {k: v for k, v in list(duplicates_by_hash.items())[:500]},
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"JSON: {json_path}"))

        # Salida en consola
        self.stdout.write("")
        self.stdout.write("Resumen:")
        self.stdout.write(f"  Total productos (activos): {summary['total_products']}")
        self.stdout.write(f"  Total ProductImage: {summary['total_product_images']}")
        self.stdout.write(self.style.WARNING(f"  Archivos faltantes (db_path no existe): {summary['missing_files']}"))
        self.stdout.write(self.style.WARNING(f"  Productos sin ninguna imagen: {summary['products_without_any_image']}"))
        self.stdout.write(f"  Productos con al menos una imagen faltante: {summary['products_with_missing_image']}")
        self.stdout.write(f"  Grupos de duplicados por hash: {summary['duplicate_groups_by_hash']} ({summary['duplicate_files_count']} archivos)")
        self.stdout.write("")
