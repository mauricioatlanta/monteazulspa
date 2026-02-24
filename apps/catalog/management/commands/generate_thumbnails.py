"""
Genera thumbnails WebP para ProductImage.
Idempotente: no regenera si ya existe. No hace upscale.
Tamaños: 300, 600, 1000 (responsive).

Requiere: pip install pillow
"""
import os

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import ProductImage

SIZES = [300, 600, 1000]


def thumb_path(orig_rel: str, width: int) -> str:
    """orig_rel: 'products/SKU/file.png' (relativo a MEDIA_ROOT)."""
    d, f = os.path.split(str(orig_rel).replace("\\", "/"))
    name, _ext = os.path.splitext(f)
    return os.path.join(d, "thumbs", f"{name}_{width}.webp").replace("\\", "/")


class Command(BaseCommand):
    help = "Genera thumbnails WebP para ProductImage. Idempotente. No upscale."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--quality", type=int, default=78)
        parser.add_argument("--limit", type=int, default=0, help="Límite de ProductImage a procesar (0=sin límite)")

    def handle(self, *args, **opts):
        apply_changes = opts["apply"]
        quality = opts["quality"]
        limit = opts["limit"]

        try:
            from PIL import Image
        except ImportError:
            self.stdout.write(self.style.ERROR("Instala Pillow: pip install pillow"))
            return

        qs = ProductImage.objects.all().only("id", "image")
        if limit:
            qs = qs[:limit]

        made = 0
        skipped = 0
        missing = 0
        errors = 0

        media_root = getattr(settings, "MEDIA_ROOT", "")
        if not media_root or not os.path.isdir(media_root):
            self.stdout.write(self.style.ERROR(f"MEDIA_ROOT no configurado o no existe: {media_root}"))
            return

        for pi in qs:
            rel = str(pi.image) if pi.image else ""
            if not rel:
                missing += 1
                continue

            src = os.path.join(media_root, rel.replace("/", os.sep))
            if not os.path.exists(src):
                missing += 1
                continue

            try:
                with Image.open(src) as im:
                    im.load()
                    w, h = im.size
                    # Calcular y crear cada tamaño (abrir una sola vez)
                    for target_w in SIZES:
                        if w <= target_w:
                            continue

                        out_rel = thumb_path(rel, target_w)
                        out_abs = os.path.join(media_root, out_rel.replace("/", os.sep))

                        if os.path.exists(out_abs):
                            skipped += 1
                            continue

                        if not apply_changes:
                            made += 1
                            continue

                        try:
                            os.makedirs(os.path.dirname(out_abs), exist_ok=True)
                            ratio = target_w / float(w)
                            target_h = int(h * ratio)
                            thumb = im.resize((target_w, target_h), Image.LANCZOS)
                            thumb.save(out_abs, "WEBP", quality=quality, method=6)
                            made += 1
                        except Exception as e:
                            self.stdout.write(self.style.WARNING(f"Error creando {out_rel}: {e}"))
                            errors += 1
            except Exception:
                errors += 1

        self.stdout.write(self.style.SUCCESS("OK"))
        if apply_changes:
            self.stdout.write(f"Creados: {made}")
        else:
            self.stdout.write(f"A crear (dry-run): {made}")
        self.stdout.write(f"Omitidos (ya existen): {skipped}")
        self.stdout.write(f"Faltantes/rotos: {missing}")
        if errors:
            self.stdout.write(self.style.WARNING(f"Errores: {errors}"))
        if not apply_changes:
            self.stdout.write(self.style.WARNING("Modo dry-run. Usa --apply para aplicar."))
