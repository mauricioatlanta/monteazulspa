"""
Reordena imágenes por producto: main primero (pos=1), resto secuencial.
Idempotente. Respeta límite de 4 imágenes por producto (position 1-4).

Para evitar conflictos con el UniqueConstraint (product, position), se eliminan
y recrean los registros en el orden correcto cuando hay cambios.
"""
import os

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import ProductImage


def is_main(path: str) -> bool:
    base = os.path.basename(str(path)).lower()
    return base.startswith("main") or "main" in base


class Command(BaseCommand):
    help = "Reordena imágenes por producto: main primero (pos=1), resto secuencial. Idempotente."

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true")
        parser.add_argument("--limit", type=int, default=0, help="Límite de productos a procesar (0=sin límite)")

    def handle(self, *args, **opts):
        apply_changes = opts["apply"]
        limit = opts["limit"]

        qs = ProductImage.objects.select_related("product").order_by("product_id", "position", "id")
        if limit:
            product_ids = list(
                ProductImage.objects.values_list("product_id", flat=True).distinct()[:limit]
            )
            qs = qs.filter(product_id__in=product_ids)

        by_product = {}
        for img in qs:
            by_product.setdefault(img.product_id, []).append(img)

        changed = 0
        for pid, imgs in by_product.items():
            mains = [i for i in imgs if is_main(i.image.name if i.image else "")]
            others = [i for i in imgs if i not in mains]
            ordered = (mains[:1] + others) if mains else imgs
            ordered = ordered[: ProductImage.MAX_IMAGES_PER_PRODUCT]

            needs_reorder = any(img.position != pos for pos, img in enumerate(ordered, start=1))
            if not needs_reorder:
                continue

            changed += 1

            if apply_changes:
                with transaction.atomic():
                    # Guardar path y metadatos antes de borrar (evita referencias obsoletas)
                    to_recreate = [
                        {
                            "image_name": img.image.name if img.image else "",
                            "alt_text": img.alt_text or "",
                            "is_primary": img.is_primary,
                        }
                        for img in ordered
                    ]
                    ProductImage.objects.filter(product_id=pid).delete()
                    for pos, data in enumerate(to_recreate, start=1):
                        if not data["image_name"]:
                            continue
                        ProductImage.objects.create(
                            product_id=pid,
                            image=data["image_name"],
                            alt_text=data["alt_text"],
                            is_primary=data["is_primary"] if pos == 1 else False,
                            position=pos,
                        )

        self.stdout.write(self.style.SUCCESS("OK"))
        self.stdout.write(f"Productos tocados: {len(by_product)}")
        msg = f"Productos reordenados: {changed}" if apply_changes else f"Productos a reordenar (dry-run): {changed}"
        self.stdout.write(msg)
        if not apply_changes:
            self.stdout.write(self.style.WARNING("Modo dry-run. Usa --apply para aplicar."))
