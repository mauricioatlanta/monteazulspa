# -*- coding: utf-8 -*-
"""
Establece los nombres de las categorías del catálogo según especificación:
  Silenciadores de Alto Flujo, Resonadores, cataliticos CLF, cataliticos TWG,
  cataliticos ensamble directo, colas de escapes.

Los slugs no se modifican (solo el campo name). Las categorías se buscan por slug.

Uso:
  python manage.py renombrar_categorias
  python manage.py renombrar_categorias --dry-run
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category

# slug (existente) -> nombre a mostrar
# Cataliticos es la categoría raíz; TWG, CLF y Ensamble Directo son subcategorías (ver estructura_categorias_cataliticos).
SLUG_TO_NAME = {
    "silenciadores": "Silenciadores de Alto Flujo",
    "resonadores": "Resonadores",
    "cataliticos": "Cataliticos",
    "cataliticos-clf": "Cataliticos CLF",
    "cataliticos-twc": "Cataliticos TWG",
    "cataliticos-twc-euro3": "Euro 3",
    "cataliticos-twc-euro4": "Euro 4",
    "cataliticos-twc-euro5": "Euro 5",
    "cataliticos-twc-diesel": "Diesel",
    "cataliticos-ensamble-directo": "Cataliticos Ensamble Directo",
    "colas-de-escape": "colas de escapes",
}


class Command(BaseCommand):
    help = "Renombra categorías del catálogo (Silenciadores de Alto Flujo, Resonadores, cataliticos CLF/TWG, etc.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se cambiaría, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        updated = 0
        for slug, new_name in SLUG_TO_NAME.items():
            cat = Category.objects.filter(slug=slug, is_active=True).first()
            if not cat:
                cat = Category.objects.filter(slug=slug).first()
            if cat:
                if cat.name != new_name:
                    old_name = cat.name
                    if not dry_run:
                        cat.name = new_name
                        cat.save(update_fields=["name"])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  {slug}: "{old_name}" -> "{new_name}"'
                            + (" (dry-run)" if dry_run else "")
                        )
                    )
                    updated += 1
            else:
                self.stdout.write(self.style.NOTICE(f"  {slug}: categoría no encontrada, omitido."))

        if dry_run:
            self.stdout.write(self.style.WARNING(f"Dry-run: {updated} categorías se actualizarían."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Listo: {updated} categorías renombradas."))
