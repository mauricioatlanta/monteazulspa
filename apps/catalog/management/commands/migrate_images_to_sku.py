"""
Migra imágenes de productos al esquema por SKU:
  products/<sku>/main.webp, 01.webp, 02.webp, ... (banner.webp opcional)

--dry-run (default): solo imprime acciones.
--apply: ejecuta movimientos y actualiza DB.
--keep-original: copia en lugar de mover (no borra origen).
--convert-webp: convierte a .webp si Pillow está disponible.
"""
import logging
import os
import re
import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.files.storage import default_storage

from apps.catalog.models import Product, ProductImage

logger = logging.getLogger(__name__)

try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


def _canonical_image_order(qs):
    """Orden: principal primero (is_primary), luego por position, luego por id."""
    return qs.order_by("-is_primary", "position", "id")


def _find_candidate_by_basename(media_root: Path, basename: str) -> list:
    """Busca en media_root archivos con el mismo basename (case-insensitive). Devuelve lista de paths relativos."""
    if not media_root or not basename:
        return []
    candidates = []
    for root, _dirs, files in os.walk(media_root):
        for f in files:
            if f.lower() == basename.lower():
                full = Path(root) / f
                try:
                    rel = full.relative_to(media_root)
                    candidates.append(str(rel).replace("\\", "/"))
                except ValueError:
                    pass
    return candidates


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _convert_to_webp(src_path: Path, dest_path: Path) -> bool:
    """Convierte imagen a WebP. Devuelve True si ok."""
    if not PILLOW_AVAILABLE:
        return False
    try:
        img = Image.open(src_path)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        _ensure_dir(dest_path.parent)
        img.save(dest_path, "WEBP", quality=85)
        return True
    except Exception:
        return False


def _extension(path_or_name: str) -> str:
    """Extrae extensión en minúsculas."""
    s = os.path.splitext(path_or_name)[1]
    return (s or "").lower()


class Command(BaseCommand):
    help = "Migra imágenes al esquema products/<sku>/main.webp, 01.webp, 02.webp..."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo imprimir acciones, no modificar.",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Ejecutar migración (mover/copiar y actualizar DB). Sin --apply es dry-run.",
        )
        parser.add_argument(
            "--keep-original",
            action="store_true",
            help="Copiar en lugar de mover; no borrar archivos origen.",
        )
        parser.add_argument(
            "--convert-webp",
            action="store_true",
            help="Convertir imágenes a .webp (requiere Pillow).",
        )

    def handle(self, *args, **options):
        dry_run = not options.get("apply", False)
        keep_original = options.get("keep_original", False)
        convert_webp = options.get("convert_webp", False) and PILLOW_AVAILABLE

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo DRY-RUN: no se modificará nada."))
        else:
            self.stdout.write(self.style.SUCCESS("Modo APPLY: se ejecutarán cambios."))
        if keep_original:
            self.stdout.write("Se mantendrán archivos origen (copia).")
        if convert_webp:
            self.stdout.write("Conversión a WebP activada.")
        elif options.get("convert_webp") and not PILLOW_AVAILABLE:
            self.stdout.write(self.style.WARNING("--convert-webp ignorado: Pillow no instalado."))

        media_root = Path(settings.MEDIA_ROOT)
        report = {"migrated": [], "missing": [], "multiple_candidates": [], "errors": []}
        already_ok = 0
        used_sources = set()

        products = Product.objects.filter(is_active=True, deleted_at__isnull=True).order_by("sku")
        for product in products:
            sku_raw = (product.sku or "").strip()
            sku_clean = re.sub(r"[^\w\-]", "", sku_raw, flags=re.IGNORECASE).strip() if sku_raw else ""
            if not sku_clean:
                sku_clean = f"product-{product.id}"
            dest_dir_rel = f"products/{sku_clean}"
            dest_dir_abs = media_root / dest_dir_rel
            images = _canonical_image_order(
                ProductImage.objects.filter(product=product).select_related("product")
            )
            if not images:
                continue

            for idx, img in enumerate(images):
                if idx == 0:
                    dest_name = "main.webp" if convert_webp else "main" + _extension(img.image.name or ".jpg")
                else:
                    dest_name = f"{idx:02d}.webp" if convert_webp else f"{idx:02d}" + _extension(img.image.name or ".jpg")
                dest_rel = f"{dest_dir_rel}/{dest_name}"
                dest_abs = media_root / dest_rel

                db_path = (img.image.name or "").strip()
                source_abs = media_root / db_path if db_path else None
                exists = source_abs and source_abs.is_file() if source_abs else False

                if not exists and db_path:
                    basename = os.path.basename(db_path)
                    candidates = _find_candidate_by_basename(media_root, basename)
                    if len(candidates) == 1:
                        source_abs = media_root / candidates[0]
                        exists = source_abs.is_file()
                        db_path = candidates[0]
                    elif len(candidates) > 1:
                        report["multiple_candidates"].append({
                            "product_id": product.id,
                            "sku": product.sku,
                            "image_id": img.pk,
                            "db_path": img.image.name,
                            "candidates": candidates,
                        })
                        self.stdout.write(
                            self.style.WARNING(
                                f"  [{product.sku}] image_id={img.pk} múltiples candidatos: {candidates[:3]}"
                            )
                        )
                        continue
                    else:
                        report["missing"].append({
                            "product_id": product.id,
                            "sku": product.sku,
                            "image_id": img.pk,
                            "db_path": img.image.name,
                        })
                        self.stdout.write(
                            self.style.ERROR(f"  [{product.sku}] image_id={img.pk} archivo no encontrado: {img.image.name}")
                        )
                        continue

                if not exists or not source_abs:
                    continue

                src_abs = source_abs.resolve()
                dest_abs_resolved = dest_abs.resolve()

                # Ya está en destino
                if src_abs == dest_abs_resolved:
                    self.stdout.write(f"  [skip] ya está en destino: {dest_rel}")
                    already_ok += 1
                    continue

                # Si el destino ya existe, no sobrescribir
                if dest_abs_resolved.exists():
                    self.stdout.write(f"  [skip] destino ya existe: {dest_rel}")
                    already_ok += 1
                    continue

                if dry_run:
                    self.stdout.write(f"  [dry-run] {source_abs} -> {dest_rel}")
                    report["migrated"].append({
                        "product_id": product.id,
                        "sku": product.sku,
                        "image_id": img.pk,
                        "from": str(source_abs),
                        "to": dest_rel,
                        "applied": False,
                    })
                    continue

                # Misma fuente usada para otro SKU → copiar, no mover
                if str(src_abs) in used_sources:
                    force_copy = True
                else:
                    used_sources.add(str(src_abs))
                    force_copy = False

                dest_abs = dest_abs_resolved
                try:
                    _ensure_dir(dest_abs.parent)
                    if convert_webp:
                        if _convert_to_webp(src_abs, dest_abs):
                            new_path = dest_rel
                        else:
                            shutil.copy2(src_abs, dest_abs)
                            new_path = dest_rel
                    else:
                        if keep_original or force_copy:
                            shutil.copy2(src_abs, dest_abs)
                        else:
                            shutil.move(str(src_abs), str(dest_abs))
                        new_path = dest_rel

                    img.image.name = new_path
                    img.save(update_fields=["image"])
                    report["migrated"].append({
                        "product_id": product.id,
                        "sku": product.sku,
                        "image_id": img.pk,
                        "from": db_path,
                        "to": new_path,
                        "applied": True,
                    })
                    self.stdout.write(self.style.SUCCESS(f"  {db_path} -> {new_path}"))
                except Exception as e:
                    report["errors"].append({
                        "product_id": product.id,
                        "sku": product.sku,
                        "image_id": img.pk,
                        "error": str(e),
                    })
                    self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        # Resumen
        self.stdout.write("")
        self.stdout.write("Resumen:")
        self.stdout.write(f"  Migrados (o planeados): {len(report['migrated'])}")
        self.stdout.write(f"  Ya en destino (skip): {already_ok}")
        self.stdout.write(f"  Faltantes: {len(report['missing'])}")
        self.stdout.write(f"  Múltiples candidatos (revisión manual): {len(report['multiple_candidates'])}")
        self.stdout.write(f"  Errores: {len(report['errors'])}")

        # Guardar reporte en reports/
        reports_dir = Path(settings.BASE_DIR) / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        import json
        report_path = reports_dir / "migrate_images_to_sku_report.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        self.stdout.write(self.style.SUCCESS(f"Reporte: {report_path}"))
