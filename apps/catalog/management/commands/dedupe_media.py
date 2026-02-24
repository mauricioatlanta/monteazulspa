"""
Deduplicación de archivos en media/products/ por hash.
Define canonical: products/<sku>/main.webp si existe, si no el path más corto.
Actualiza referencias en ProductImage al canonical y opcionalmente elimina duplicados (--apply).
"""
import hashlib
import os
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import ProductImage


def _file_hash(path: Path, chunk_size: int = 8192) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _collect_hashes(media_root: Path, subdir: str = "products") -> dict:
    """Devuelve { hash: [ (rel_path, abs_path), ... ] } para todos los archivos en subdir."""
    by_hash = {}
    base = media_root / subdir
    if not base.exists():
        return by_hash
    for root, _dirs, files in os.walk(base):
        for name in files:
            abs_path = Path(root) / name
            try:
                digest = _file_hash(abs_path)
                rel = abs_path.relative_to(media_root)
                rel_str = str(rel).replace("\\", "/")
                by_hash.setdefault(digest, []).append((rel_str, abs_path))
            except (OSError, ValueError):
                continue
    return by_hash


def _choose_canonical(paths: list) -> str:
    """
    paths = [ (rel_path, abs_path), ... ]
    Canonical: el que esté en products/<sku>/main.webp (o main.*), si no el path más corto.
    """
    def key(item):
        rel, _ = item
        parts = rel.split("/")
        # products/SKU/main.webp -> (0, 0); products/SKU/01.webp -> (0, 1); path largo -> (1, len)
        if len(parts) >= 3:
            name = parts[-1].lower()
            if name == "main.webp" or name.startswith("main."):
                return (0, 0)
            if name and name[0].isdigit():
                return (0, 1)
        return (1, len(rel))
    sorted_paths = sorted(paths, key=key)
    return sorted_paths[0][0]


class Command(BaseCommand):
    help = "Deduplica archivos en media/products/ por hash; actualiza DB al canonical; --apply elimina duplicados."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Eliminar archivos duplicados después de actualizar DB. Sin --apply solo actualiza DB.",
        )

    def handle(self, *args, **options):
        apply_delete = options.get("apply", False)
        media_root = Path(settings.MEDIA_ROOT)

        by_hash = _collect_hashes(media_root)
        duplicates = {h: paths for h, paths in by_hash.items() if len(paths) > 1}

        if not duplicates:
            self.stdout.write("No hay duplicados por hash en media/products/.")
            return

        updated_count = 0
        deleted_count = 0

        for digest, paths in duplicates.items():
            canonical_rel = _choose_canonical(paths)
            canonical_abs = media_root / canonical_rel.replace("/", os.sep)
            others = [rel for rel, _ in paths if rel != canonical_rel]

            # ProductImage que apuntan a alguno de "others" -> actualizar a canonical
            for rel in others:
                qs = ProductImage.objects.filter(image=rel)
                for img in qs:
                    self.stdout.write(f"  Actualizar DB: {rel} -> {canonical_rel} (image_id={img.pk})")
                    img.image.name = canonical_rel
                    img.save(update_fields=["image"])
                    updated_count += 1

            # Opcional: borrar archivos duplicados (no el canonical)
            if apply_delete:
                for rel in others:
                    abs_path = media_root / rel.replace("/", os.sep)
                    if abs_path.is_file():
                        try:
                            abs_path.unlink()
                            self.stdout.write(self.style.SUCCESS(f"  Eliminado: {rel}"))
                            deleted_count += 1
                        except OSError as e:
                            self.stdout.write(self.style.ERROR(f"  Error eliminando {rel}: {e}"))

        self.stdout.write("")
        self.stdout.write(f"Grupos duplicados: {len(duplicates)}")
        self.stdout.write(f"Referencias DB actualizadas: {updated_count}")
        if apply_delete:
            self.stdout.write(f"Archivos eliminados: {deleted_count}")
        else:
            self.stdout.write("Para eliminar archivos duplicados en disco, ejecuta con --apply.")
