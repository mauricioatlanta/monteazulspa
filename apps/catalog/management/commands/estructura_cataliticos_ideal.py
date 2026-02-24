# -*- coding: utf-8 -*-
"""
Crea la estructura ideal definitiva para Convertidores Catalíticos:

  Convertidores Catalíticos (raíz)
  ├── TWG (Universal)
  │   ├── Bencina     <- productos con euro_norm Euro2/3/4/5 (la norma es filtro, no categoría)
  │   └── Diesel
  └── Ensamble Directo (CLF)
      ├── Chevrolet
      ├── Hyundai
      ├── Toyota
      └── Otros

Uso:
  python manage.py estructura_cataliticos_ideal
  python manage.py estructura_cataliticos_ideal --dry-run

Nota: Este comando crea las categorías con slugs nuevos (cataliticos-twg-universal,
cataliticos-twg-bencina, cataliticos-twg-diesel, cataliticos-clf-chevrolet, etc.).
La migración de productos desde la estructura actual (Euro3/Euro4/Euro5) a Bencina
puede hacerse con un comando aparte o manualmente.
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category

CATALITICOS_ROOT_SLUG = "cataliticos"

# Estructura: (slug, nombre, hijos opcionales)
TWG_UNIVERSAL_SLUG = "cataliticos-twg-universal"
TWG_BENCINA_SLUG = "cataliticos-twg-bencina"
TWG_DIESEL_SLUG = "cataliticos-twg-diesel"

ENSMABLE_DIRECTO_SLUG = "cataliticos-ensamble-directo"
# Nombres con sufijo (CLF) para no colisionar con Category.name unique
CLF_MARCAS = (
    ("cataliticos-clf-chevrolet", "Chevrolet (CLF)"),
    ("cataliticos-clf-hyundai", "Hyundai (CLF)"),
    ("cataliticos-clf-toyota", "Toyota (CLF)"),
    ("cataliticos-clf-otros", "Otros (CLF)"),
)


class Command(BaseCommand):
    help = "Crea estructura ideal: TWG (Universal) → Bencina/Diesel; Ensamble Directo → Chevrolet, Hyundai, Toyota, Otros."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        root = Category.objects.filter(slug=CATALITICOS_ROOT_SLUG, parent__isnull=True).first()
        if not root:
            if not dry_run:
                root = Category.objects.create(
                    name="Convertidores Catalíticos",
                    slug=CATALITICOS_ROOT_SLUG,
                    parent=None,
                    is_active=True,
                )
                self.stdout.write(self.style.SUCCESS("Creada raíz: Convertidores Catalíticos"))
            else:
                self.stdout.write(self.style.NOTICE("Se crearía raíz Convertidores Catalíticos. Ejecuta sin --dry-run."))
                return
        else:
            if root.name != "Convertidores Catalíticos" and not dry_run:
                root.name = "Convertidores Catalíticos"
                root.save(update_fields=["name"])
                self.stdout.write(self.style.SUCCESS("Actualizada raíz: Convertidores Catalíticos"))

        # TWG (Universal) -> Bencina, Diesel
        twg, created = Category.objects.get_or_create(
            slug=TWG_UNIVERSAL_SLUG,
            defaults={
                "name": "TWG (Universal)",
                "parent": root,
                "is_active": True,
            },
        )
        if not dry_run and not created:
            if twg.parent_id != root.id:
                twg.parent = root
                twg.save(update_fields=["parent"])
            if twg.name != "TWG (Universal)":
                twg.name = "TWG (Universal)"
                twg.save(update_fields=["name"])
        self.stdout.write(self.style.SUCCESS(f"  {'Creada' if created else 'Actualizada'}: TWG (Universal)"))

        # Nombres únicos: Category.name es unique; puede existir ya "Diesel" o "Bencina" en otra rama
        for slug_child, name_child in (
            (TWG_BENCINA_SLUG, "Bencina (TWG)"),
            (TWG_DIESEL_SLUG, "Diesel (TWG)"),
        ):
            child, c = Category.objects.get_or_create(
                slug=slug_child,
                defaults={"name": name_child, "parent": twg, "is_active": True},
            )
            if not dry_run and not c:
                if child.parent_id != twg.id:
                    child.parent = twg
                    child.save(update_fields=["parent"])
                if child.name != name_child:
                    child.name = name_child
                    child.save(update_fields=["name"])
            self.stdout.write(self.style.SUCCESS(f"    → {name_child} ({slug_child})"))

        # Ensamble Directo (CLF) -> Chevrolet, Hyundai, Toyota, Otros
        ensamble = Category.objects.filter(slug=ENSMABLE_DIRECTO_SLUG).first()
        if not ensamble:
            if not dry_run:
                ensamble = Category.objects.create(
                    name="Ensamble Directo (CLF)",
                    slug=ENSMABLE_DIRECTO_SLUG,
                    parent=root,
                    is_active=True,
                )
                self.stdout.write(self.style.SUCCESS("  Creada: Ensamble Directo (CLF)"))
            else:
                ensamble = None
                self.stdout.write(self.style.SUCCESS("  [dry-run] Se crearía: Ensamble Directo (CLF)"))
        else:
            if not dry_run:
                if ensamble.parent_id != root.id:
                    ensamble.parent = root
                    ensamble.save(update_fields=["parent"])
                if ensamble.name != "Ensamble Directo (CLF)":
                    ensamble.name = "Ensamble Directo (CLF)"
                    ensamble.save(update_fields=["name"])
            self.stdout.write(self.style.SUCCESS("  Actualizada: Ensamble Directo (CLF)"))

        if ensamble:
            for slug_marca, name_marca in CLF_MARCAS:
                child, c = Category.objects.get_or_create(
                    slug=slug_marca,
                    defaults={"name": name_marca, "parent": ensamble, "is_active": True},
                )
                if not dry_run and not c:
                    if child.parent_id != ensamble.id:
                        child.parent = ensamble
                        child.save(update_fields=["parent"])
                    if child.name != name_marca:
                        child.name = name_marca
                        child.save(update_fields=["name"])
                self.stdout.write(self.style.SUCCESS(f"    → {name_marca} ({slug_marca})"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar cambios."))
        else:
            self.stdout.write(self.style.SUCCESS("Listo: estructura ideal de catalíticos aplicada."))
