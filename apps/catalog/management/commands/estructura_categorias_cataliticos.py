# -*- coding: utf-8 -*-
"""
Estructura la categoría Cataliticos: crea la categoría raíz "Cataliticos" y deja como
subcategorías a Cataliticos TWG, Cataliticos CLF y Cataliticos Ensamble Directo.

Estructura resultante:
  Cataliticos (raíz)
  ├── Cataliticos TWG (y sus subcategorías Euro 3, Euro 4, Euro 5, Diesel)
  ├── Cataliticos CLF
  └── Cataliticos Ensamble Directo

Uso:
  python manage.py estructura_categorias_cataliticos
  python manage.py estructura_categorias_cataliticos --dry-run
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category


# Slug y nombre de la categoría raíz
CATALITICOS_ROOT_SLUG = "cataliticos"
CATALITICOS_ROOT_NAME = "Cataliticos"

# Subcategorías de Cataliticos (slug -> nombre)
SUBCATS = {
    "cataliticos-twc": "Cataliticos TWG",
    "cataliticos-clf": "Cataliticos CLF",
    "cataliticos-ensamble-directo": "Cataliticos Ensamble Directo",
}


class Command(BaseCommand):
    help = "Estructura Cataliticos como categoría raíz con TWG, CLF y Ensamble Directo como subcategorías."

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

        # 1) Obtener o crear la categoría raíz "Cataliticos"
        if dry_run:
            root = Category.objects.filter(slug=CATALITICOS_ROOT_SLUG).first()
            if not root:
                self.stdout.write(self.style.SUCCESS(f"  [dry-run] Se crearía categoría raíz: {CATALITICOS_ROOT_NAME}"))
                self.stdout.write(self.style.NOTICE("  Ejecuta sin --dry-run para crear la raíz y asignar subcategorías."))
                return
        else:
            root, created = Category.objects.get_or_create(
                slug=CATALITICOS_ROOT_SLUG,
                defaults={
                    "name": CATALITICOS_ROOT_NAME,
                    "parent": None,
                    "is_active": True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Creada categoría raíz: {CATALITICOS_ROOT_NAME}"))
            else:
                if root.parent_id is not None or root.name != CATALITICOS_ROOT_NAME or not root.is_active:
                    root.parent = None
                    root.name = CATALITICOS_ROOT_NAME
                    root.is_active = True
                    root.save(update_fields=["parent", "name", "is_active"])
                    self.stdout.write(self.style.SUCCESS(f"  Actualizada categoría raíz: {CATALITICOS_ROOT_NAME}"))

        # 2) Asignar cada subcategoría como hija de Cataliticos (crear si no existe)
        for slug_sub, name_sub in SUBCATS.items():
            cat = Category.objects.filter(slug=slug_sub).first()
            if not cat:
                if not dry_run:
                    cat = Category.objects.create(
                        name=name_sub,
                        slug=slug_sub,
                        parent=root,
                        is_active=True,
                    )
                    self.stdout.write(self.style.SUCCESS(f"  Creada subcategoría: {name_sub} (parent: {root.name})"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"  [dry-run] Se crearía subcategoría: {name_sub}"))
                continue
            changed = False
            updates = {}
            if cat.parent_id != root.id:
                updates["parent"] = root
                changed = True
            if not cat.is_active:
                updates["is_active"] = True
                changed = True
            if cat.name != name_sub:
                updates["name"] = name_sub
                changed = True
            if changed and not dry_run:
                for k, v in updates.items():
                    setattr(cat, k, v)
                cat.save(update_fields=list(updates.keys()))
            if changed:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  Actualizada {slug_sub}: parent=Cataliticos, name={name_sub}"
                        + (" (dry-run)" if dry_run else "")
                    )
                )

        # 3) Cataliticos TWG: crear o asegurar subcategorías Euro 3, Euro 4, Euro 5, Diesel
        cat_twc = Category.objects.filter(slug="cataliticos-twc", is_active=True).first()
        if cat_twc:
            for label, slug_suffix in (
                ("Euro 3", "euro3"),
                ("Euro 4", "euro4"),
                ("Euro 5", "euro5"),
                ("Diesel", "diesel"),
            ):
                slug_child = f"cataliticos-twc-{slug_suffix}"
                if dry_run:
                    exists = Category.objects.filter(slug=slug_child).exists()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Subcategoría TWG: {label} ({slug_child})"
                            + (" [ya existe]" if exists else " [se crearía]")
                        )
                    )
                    continue
                child, created = Category.objects.get_or_create(
                    slug=slug_child,
                    defaults={
                        "name": label,
                        "parent": cat_twc,
                        "is_active": True,
                    },
                )
                if not created:
                    if child.parent_id != cat_twc.id:
                        child.parent = cat_twc
                        child.save(update_fields=["parent"])
                    if not child.is_active:
                        child.is_active = True
                        child.save(update_fields=["is_active"])
                self.stdout.write(
                    self.style.SUCCESS(f"  Subcategoría TWG: {label} ({slug_child})")
                )
        else:
            self.stdout.write(
                self.style.NOTICE("  No se encontró 'Cataliticos TWG' para crear Euro 3/4/5/Diesel.")
            )

        if dry_run:
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar cambios."))
        else:
            self.stdout.write(self.style.SUCCESS("Listo: estructura Cataliticos aplicada."))
