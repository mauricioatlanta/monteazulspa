"""
Elimina ProductImage que apuntan a archivos que no existen en disco.

Ejemplo: products/2026/... que ya no existen tras la migración por SKU.

--dry-run (default): lista los registros que se borrarían.
--apply: elimina esos ProductImage de la BD.
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import ProductImage


class Command(BaseCommand):
    help = "Elimina ProductImage cuyo archivo no existe en media (dry-run por defecto)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Ejecutar borrado en BD. Sin --apply es dry-run.",
        )

    def handle(self, *args, **options):
        apply = options.get("apply", False)
        dry_run = not apply

        if dry_run:
            self.stdout.write(self.style.WARNING("Modo DRY-RUN: no se borrará nada."))
        else:
            self.stdout.write(self.style.SUCCESS("Modo APPLY: se eliminarán los ProductImage rotos."))

        media_root = Path(settings.MEDIA_ROOT)
        to_delete = []
        for img in ProductImage.objects.select_related("product").all():
            path = (img.image.name or "").strip()
            if not path:
                continue
            full_path = media_root / path
            if not full_path.is_file():
                to_delete.append(img)

        if not to_delete:
            self.stdout.write("No hay ProductImage con archivo faltante.")
            return

        for img in to_delete:
            self.stdout.write(
                f"  product_id={img.product_id} sku={img.product.sku} image_id={img.pk} -> {img.image.name}"
            )

        self.stdout.write("")
        self.stdout.write(f"Total: {len(to_delete)} ProductImage con archivo faltante.")

        if apply:
            ids = [img.pk for img in to_delete]
            deleted, _ = ProductImage.objects.filter(pk__in=ids).delete()
            self.stdout.write(self.style.SUCCESS(f"Eliminados: {deleted}"))
        else:
            self.stdout.write("Ejecuta con --apply para eliminar estos registros.")
