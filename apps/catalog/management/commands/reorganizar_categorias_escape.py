from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Product, Category


class Command(BaseCommand):
    help = "Crea categorías nuevas (DW/LT/LTM) y reasigna productos según prefijo de SKU."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guarda cambios, solo muestra lo que haría.")
        parser.add_argument("--limit", type=int, default=0, help="Limita cantidad de productos a procesar (debug).")
        parser.add_argument(
            "--deactivate-old",
            action="store_true",
            help="Desactiva categorías antiguas 'Resonadores' y 'Silenciadores Alto Flujo' si existen.",
        )

    def _get_or_create_category(self, name: str, slug: str):
        obj, created = Category.objects.get_or_create(
            slug=slug,
            defaults={
                "name": name,
                "parent": None,
                "is_active": True,
            },
        )
        changed = False
        if obj.name != name:
            obj.name = name
            changed = True
        if obj.parent_id is not None:
            obj.parent = None
            changed = True
        if obj.is_active is False:
            obj.is_active = True
            changed = True
        if changed:
            obj.save()
        return obj, created, changed

    def _deactivate_if_exists(self, name: str):
        qs = Category.objects.filter(name__iexact=name)
        count = qs.count()
        if count:
            qs.update(is_active=False)
        return count

    @transaction.atomic
    def handle(self, *args, **opts):
        dry = opts["dry_run"]
        limit = opts["limit"] or 0
        deactivate_old = opts["deactivate_old"]

        # 1) Categorías (sin siglas DW/LT/LTM en el nombre)
        cat_dw, c1, u1 = self._get_or_create_category("Silenciadores", "silenciador-linea-dw")
        cat_lt, c2, u2 = self._get_or_create_category("Silenciadores Alto Flujo", "silenciador-alto-flujo-lt")
        cat_ltm, c3, u3 = self._get_or_create_category(
            "Resonadores Deportivo Alto Flujo", "resonador-deportivo-alto-flujo-ltm"
        )

        self.stdout.write("=== Categorías nuevas ===")
        self.stdout.write(f"- {cat_dw.name} ({cat_dw.slug})  created={c1} updated={u1}")
        self.stdout.write(f"- {cat_lt.name} ({cat_lt.slug})  created={c2} updated={u2}")
        self.stdout.write(f"- {cat_ltm.name} ({cat_ltm.slug}) created={c3} updated={u3}")

        # 2) Reasignación de productos por prefijo SKU (LTM primero porque empieza con LT)
        qs = Product.objects.all().only("id", "sku", "category_id")
        if limit:
            qs = qs.order_by("id")[:limit]

        moved = {"LTM": 0, "LT": 0, "DW": 0}
        unchanged = 0
        skipped = 0

        for p in qs:
            sku = (p.sku or "").strip().upper()
            if not sku:
                skipped += 1
                continue
            if sku.startswith("LTM"):
                target = cat_ltm
                key = "LTM"
            elif sku.startswith("LT"):
                target = cat_lt
                key = "LT"
            elif sku.startswith("DW"):
                target = cat_dw
                key = "DW"
            else:
                skipped += 1
                continue
            if p.category_id == target.id:
                unchanged += 1
                continue
            moved[key] += 1
            self.stdout.write(f"#{p.id} SKU={sku} -> {target.slug}")
            if not dry:
                p.category = target
                p.save(update_fields=["category"])

        old_deactivated = {}
        if deactivate_old and not dry:
            old_deactivated["Resonadores"] = self._deactivate_if_exists("Resonadores")
            old_deactivated["Silenciadores Alto Flujo"] = self._deactivate_if_exists("Silenciadores Alto Flujo")

        self.stdout.write(self.style.SUCCESS("=== RESUMEN ==="))
        self.stdout.write(f"Movidos LTM: {moved['LTM']}")
        self.stdout.write(f"Movidos LT : {moved['LT']}")
        self.stdout.write(f"Movidos DW : {moved['DW']}")
        self.stdout.write(f"Sin cambio : {unchanged}")
        self.stdout.write(f"Saltados   : {skipped}")

        if deactivate_old:
            if dry:
                self.stdout.write("DRY-RUN: (no se desactivaron categorías antiguas)")
            else:
                self.stdout.write("=== Categorías antiguas desactivadas ===")
                for k, v in old_deactivated.items():
                    self.stdout.write(f"- {k}: {v} encontradas/desactivadas")

        if dry:
            raise SystemExit("DRY-RUN: No se guardaron cambios.")
