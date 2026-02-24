# -*- coding: utf-8 -*-
"""
Fusiona las categorías "Silenciadores Alto Flujo" y "Silenciadores de Alto Flujo" en una sola,
con nombre "Silenciadores de Alto Flujo" y slug "silenciadores-alto-flujo".
Mueve todos los productos a la categoría destino sin duplicar.

Uso:
  python manage.py merge_silenciadores_alto_flujo
  python manage.py merge_silenciadores_alto_flujo --dry-run
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product

# Slugs y nombres que representan la misma subcategoría
SILENCIADORES_ALTO_FLUJO_SLUGS = ("silenciadores-alto-flujo", "silenciadores-de-alto-flujo", "silenciadores")
TARGET_SLUG = "silenciadores-alto-flujo"
TARGET_NAME = "Silenciadores de Alto Flujo"


def _is_silenciadores_alto_flujo(cat):
    """True si la categoría es una variante de Silenciadores Alto Flujo."""
    if cat.slug in SILENCIADORES_ALTO_FLUJO_SLUGS:
        return True
    name_lower = (cat.name or "").lower()
    return "silenciador" in name_lower and "alto flujo" in name_lower


class Command(BaseCommand):
    help = "Fusiona Silenciadores Alto Flujo y Silenciadores de Alto Flujo en una sola categoría."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se haría, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        # Buscar todas las categorías que representan silenciadores alto flujo (por slug o nombre)
        from django.db.models import Q

        by_slug = list(
            Category.objects.filter(
                slug__in=SILENCIADORES_ALTO_FLUJO_SLUGS,
                is_active=True,
            )
        )
        by_name = list(
            Category.objects.filter(
                is_active=True,
                name__icontains="silenciador",
            ).filter(name__icontains="alto flujo")
        )
        seen = set()
        candidates = []
        for c in by_slug + by_name:
            if c.id not in seen and _is_silenciadores_alto_flujo(c):
                seen.add(c.id)
                candidates.append(c)
        candidates.sort(key=lambda x: (0 if x.slug == TARGET_SLUG else 1, x.slug))

        if not candidates:
            self.stdout.write(
                self.style.NOTICE("No hay categorías de silenciadores alto flujo (slug silenciadores o silenciadores-alto-flujo).")
            )
            return

        if len(candidates) == 1:
            cat = candidates[0]
            if cat.name != TARGET_NAME or cat.slug != TARGET_SLUG:
                if not dry_run:
                    cat.name = TARGET_NAME
                    if cat.slug != TARGET_SLUG:
                        cat.slug = TARGET_SLUG
                        cat.save(update_fields=["name", "slug"])
                    else:
                        cat.save(update_fields=["name"])
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Una sola categoría: actualizando nombre a «{TARGET_NAME}»"
                        + (" (dry-run)" if dry_run else "")
                    )
                )
            else:
                self.stdout.write(self.style.NOTICE("  Ya hay una sola categoría con el nombre correcto."))
            return

        # Hay 2 o más: elegir destino y fusionar
        target = next(
            (c for c in candidates if c.slug == TARGET_SLUG),
            candidates[0],
        )
        sources = [c for c in candidates if c.id != target.id]

        self.stdout.write(f"  Categoría destino: {target.name} (slug={target.slug}, id={target.id})")
        for s in sources:
            self.stdout.write(f"  Categoría a fusionar: {s.name} (slug={s.slug}, id={s.id})")

        total_moved = 0
        for src in sources:
            count = Product.objects.filter(category=src).count()
            total_moved += count
            self.stdout.write(f"    -> {count} productos en «{src.name}» se moverán a «{target.name}»")

            if not dry_run and count > 0:
                Product.objects.filter(category=src).update(category=target)

        if not dry_run:
            # Renombrar fuentes primero para liberar el nombre único (evitar IntegrityError)
            for src in sources:
                src.name = f"{TARGET_NAME} [fusionado id={src.id}]"
                src.save(update_fields=["name"])

            target.name = TARGET_NAME
            if target.slug != TARGET_SLUG:
                target.slug = TARGET_SLUG
                target.save(update_fields=["name", "slug"])
            else:
                target.save(update_fields=["name"])

            for src in sources:
                # Verificar que no queden productos antes de eliminar
                remaining = Product.objects.filter(category=src).count()
                if remaining == 0:
                    src.is_active = False
                    src.save(update_fields=["is_active"])
                    self.stdout.write(self.style.SUCCESS(f"  Desactivada categoría «{src.name}» (id={src.id})"))
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  No se desactivó «{src.name}»: aún tiene {remaining} productos."
                        )
                    )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry-run: se moverían {total_moved} productos y se fusionarían {len(sources)} categorías."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Listo: {total_moved} productos movidos a «{TARGET_NAME}», {len(sources)} categorías fusionadas."
                )
            )
