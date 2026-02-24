# -*- coding: utf-8 -*-
"""
Deja en la categoría Flexibles solo productos que realmente son flexibles.
El resto se mueve a otra categoría (por defecto Colas De Escape).

Criterio "es flexible": nombre contiene "flexible" o "reforzado", o SKU es medida
(ej. 2X6, 1.75X8, 2.5X6, 2X6EXT, 2X8EXT-REF).
Uso: python manage.py limpiar_categoria_flexibles [--dry-run] [--move-to=slug]
"""
import re

from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product


def _es_flexible(product):
    """
    True si el producto se considera flexible por nombre o SKU.
    - Nombre: contiene "flexible" o "reforzado"
    - SKU: patrón medida (1.75X6, 2X8, 2,5X6) o extensión (2X6EXT, 2X8EXT-REF, etc.)
    """
    name = (product.name or "").lower()
    sku = (product.sku or "").strip().upper()
    if "flexible" in name or "reforzado" in name:
        return True
    sku_norm = sku.replace(",", ".")
    # Medida: dígitos opcional . más dígitos, luego X (con o sin guiones), luego dígitos (ej. 2X6, 1.75X8, 1.75-X-10)
    if re.match(r"^[\d]+(\.[\d]+)?\s*X\s*[\d]+", sku_norm):
        return True
    if re.match(r"^[\d]+(\.[\d]+)?X[\d]+", sku_norm):
        return True
    if re.match(r"^[\d]+(\.[\d]+)?-X-[\d]+", sku_norm):
        return True
    # Extensiones de tubo flexible (2X6EXT, 2X8EXT-REF)
    if re.match(r"^[\d]+X[\d]+(EXT|EXT-REF)?", sku_norm):
        return True
    return False


class Command(BaseCommand):
    help = "Deja en Flexibles solo productos flexibles; el resto se mueve a otra categoría."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo listar cambios, no guardar.",
        )
        parser.add_argument(
            "--move-to",
            type=str,
            default="colas-de-escape",
            help="Slug de la categoría a la que mover los no flexibles (default: colas-de-escape).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        move_to_slug = options["move_to"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        cat_flex = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat_flex:
            cat_flex = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat_flex:
            self.stderr.write(self.style.ERROR("No existe la categoría Flexibles."))
            return

        cat_dest = Category.objects.filter(slug=move_to_slug, is_active=True).first()
        if not cat_dest:
            cat_dest = Category.objects.filter(name__iexact=move_to_slug.replace("-", " ").title(), is_active=True).first()
        if not cat_dest:
            self.stderr.write(self.style.ERROR(f"No existe la categoría con slug '{move_to_slug}'."))
            return

        products = Product.objects.filter(category=cat_flex).order_by("sku")
        quedan = []
        sacados = []
        for p in products:
            if _es_flexible(p):
                quedan.append(p)
            else:
                sacados.append(p)

        self.stdout.write(f"Categoría Flexibles: {products.count()} productos actualmente.")
        self.stdout.write(f"  Se quedan (son flexibles): {len(quedan)}")
        self.stdout.write(f"  Se mueven a '{cat_dest.name}': {len(sacados)}")
        if sacados:
            self.stdout.write("")
            for p in sacados:
                self.stdout.write(f"  -> {p.sku} | {p.name[:50]}")

        if dry_run or not sacados:
            if dry_run and sacados:
                self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar."))
            return

        n = Product.objects.filter(pk__in=[p.pk for p in sacados]).update(category=cat_dest)
        self.stdout.write(self.style.SUCCESS(f"Listo: {n} productos movidos a {cat_dest.name}."))
