"""
Deduplica productos por norm_key(sku): mueve imágenes al canónico y desactiva duplicados.
Genera CSV con las acciones realizadas o simuladas.

Ej: 1,75-X-4 y 1.75X4 son el mismo producto. La clave normalizada unifica formatos.
"""
import csv
import re
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count

from apps.catalog.models import Product, ProductImage


def norm_key(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().upper().replace(",", ".")
    s = re.sub(r"(\d+)\.(\d{1,2})", r"\1\2", s)  # 1.75->175 ; 10.7->107
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def pick_canonical(products):
    """
    Heurística simple:
    1) preferir sku sin coma
    2) preferir sku más corto
    3) preferir el que tenga más imágenes
    4) id menor
    """
    def score(p):
        sku = (p.sku or "")
        comma = ("," in sku)
        img_count = getattr(p, "_img_count", 0)
        return (comma, len(sku), -img_count, p.id)

    return sorted(products, key=score)[0]


class Command(BaseCommand):
    help = "Deduplica productos por norm_key(sku): mueve imágenes al canónico y desactiva duplicados. Genera CSV."

    def add_arguments(self, parser):
        parser.add_argument("--out", default="dedupe_products_report.csv")
        parser.add_argument("--apply", action="store_true")

    def handle(self, *args, **opts):
        out = opts["out"]
        apply_changes = opts["apply"]

        with transaction.atomic():
            # 1) Agrupar por norm_key
            groups = defaultdict(list)
            qs = Product.objects.all().only("id", "sku", "name")
            for p in qs:
                k = norm_key(p.sku)
                if k:
                    groups[k].append(p)

            dup_groups = {k: v for k, v in groups.items() if len(v) > 1}

            if not dup_groups:
                self.stdout.write("No hay grupos de duplicados.")
                with open(out, "w", newline="", encoding="utf-8") as fp:
                    w = csv.writer(fp)
                    w.writerow(["action", "norm_key", "canonical_id", "canonical_sku", "dup_id", "dup_sku", "detail"])
                self.stdout.write(f"Reporte vacío: {out}")
                return

            # 2) Contar imágenes por producto (para la heurística)
            img_counts = dict(
                ProductImage.objects.values("product_id").annotate(c=Count("id")).values_list("product_id", "c")
            )

            for k, plist in dup_groups.items():
                for p in plist:
                    p._img_count = img_counts.get(p.id, 0)

            rows = []
            moved_images = 0
            deactivated = 0
            skipped_slots = 0

            for k, plist in sorted(dup_groups.items(), key=lambda x: (-len(x[1]), x[0])):
                canonical = pick_canonical(plist)
                duplicates = [p for p in plist if p.id != canonical.id]

                # Posiciones ya usadas por el canónico (1-4)
                canon_positions = set(
                    ProductImage.objects.filter(product_id=canonical.id).values_list("position", flat=True)
                )
                canon_img_paths = set(
                    ProductImage.objects.filter(product_id=canonical.id).values_list("image", flat=True)
                )
                # normalizar paths para comparación
                canon_img_paths = {str(p) if p else "" for p in canon_img_paths}

                for d in duplicates:
                    d_imgs = list(ProductImage.objects.filter(product_id=d.id).order_by("position", "id"))

                    for img in d_imgs:
                        img_path = str(img.image) if img.image else ""
                        if img_path in canon_img_paths:
                            rows.append([
                                "skip_image_duplicate", k, canonical.id, canonical.sku, d.id, d.sku, img_path
                            ])
                            continue

                        # Buscar siguiente slot libre (1-4)
                        next_pos = None
                        for pos in range(1, ProductImage.MAX_IMAGES_PER_PRODUCT + 1):
                            if pos not in canon_positions:
                                next_pos = pos
                                break

                        if next_pos is None:
                            rows.append([
                                "skip_image_no_slot", k, canonical.id, canonical.sku, d.id, d.sku, img_path
                            ])
                            skipped_slots += 1
                            continue

                        rows.append(["move_image", k, canonical.id, canonical.sku, d.id, d.sku, img_path])

                        if apply_changes:
                            img.product_id = canonical.id
                            img.position = next_pos
                            img.save(update_fields=["product", "position"])
                            moved_images += 1
                            canon_positions.add(next_pos)
                            canon_img_paths.add(img_path)

                    # Desactivar duplicado
                    rows.append(["deactivate_duplicate", k, canonical.id, canonical.sku, d.id, d.sku, ""])
                    if apply_changes:
                        d.is_active = False
                        d.save(update_fields=["is_active"])
                        deactivated += 1

            with open(out, "w", newline="", encoding="utf-8") as fp:
                w = csv.writer(fp)
                w.writerow(["action", "norm_key", "canonical_id", "canonical_sku", "dup_id", "dup_sku", "detail"])
                w.writerows(rows)

        self.stdout.write(self.style.SUCCESS("OK"))
        self.stdout.write(f"Grupos duplicados: {len(dup_groups)}")
        if apply_changes:
            self.stdout.write(f"Imágenes movidas: {moved_images}")
            self.stdout.write(f"Duplicados desactivados: {deactivated}")
            if skipped_slots:
                self.stdout.write(f"Imágenes sin slot (canónico lleno): {skipped_slots}")
        self.stdout.write(f"Reporte: {out}")
        if not apply_changes:
            self.stdout.write(self.style.WARNING("Modo dry-run. Usa --apply para aplicar cambios."))
