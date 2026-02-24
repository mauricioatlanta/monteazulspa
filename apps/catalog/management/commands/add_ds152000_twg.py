# -*- coding: utf-8 -*-
"""
Añade "Certificados DS 15/2000 MTT" a la ficha técnica de todos los catalíticos TWG.
Los catalíticos TWG son productos en categorías cataliticos-twc, cataliticos-twc-euro3, etc.

Uso:
  python manage.py add_ds152000_twg
  python manage.py add_ds152000_twg --dry-run
"""
from django.core.management.base import BaseCommand
from apps.catalog.models import Product, Category

CERT_TEXTO = "Certificados DS 15/2000 MTT"
# Variantes para detectar si ya está
CERT_VARIANTES = ("DS 15/2000", "DS 15/2000 MTT")


def _ya_tiene_cert(ficha: str) -> bool:
    """True si la ficha ya menciona la certificación."""
    if not (ficha or "").strip():
        return False
    txt = (ficha or "").lower()
    return any(v.lower() in txt for v in CERT_VARIANTES)


def _añadir_cert(ficha: str) -> str:
    """Añade la certificación al inicio de la ficha."""
    ficha = (ficha or "").strip()
    if not ficha:
        return CERT_TEXTO
    return f"{CERT_TEXTO}. {ficha}"


class Command(BaseCommand):
    help = "Añade 'Certificados DS 15/2000 MTT' a la ficha técnica de todos los catalíticos TWG."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guardar cambios.")

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        # Categorías TWG: cataliticos-twc y sus hijos (euro3, euro4, euro5, diesel)
        twg_slugs = (
            "cataliticos-twc",
            "cataliticos-twc-euro3",
            "cataliticos-twc-euro4",
            "cataliticos-twc-euro5",
            "cataliticos-twc-diesel",
        )
        cat_ids = list(
            Category.objects.filter(slug__in=twg_slugs, is_active=True).values_list("id", flat=True)
        )
        if not cat_ids:
            self.stderr.write(self.style.ERROR("No se encontraron categorías TWG."))
            return

        products = Product.objects.filter(
            category_id__in=cat_ids,
            deleted_at__isnull=True,
        ).select_related("category").order_by("sku")

        updated = 0
        skipped = 0

        for p in products:
            if _ya_tiene_cert(p.ficha_tecnica):
                skipped += 1
                continue
            self.stdout.write(f"  {p.sku} | {p.category.slug} | actualizando ficha")
            if not dry_run:
                p.ficha_tecnica = _añadir_cert(p.ficha_tecnica)
                p.save(update_fields=["ficha_tecnica", "updated_at"])
            updated += 1

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Listo: {updated} productos actualizados, {skipped} ya tenían la certificación."))
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardaron cambios. Quita --dry-run para aplicar."))
