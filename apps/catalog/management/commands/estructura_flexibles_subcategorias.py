# -*- coding: utf-8 -*-
"""
Estructura subcategorías de Flexibles:
- Flexibles (raíz): menú de elección
- Flexibles (normales): todos los flexibles excepto con extensión
- Flexibles con extensión: 2x6 y 2x8 con extensión (2X6EXT-REF, 2X8EXT-REF)

Incluye productos de: flexibles, flexibles-reforzados, tubos-flexibles y sus descendientes.
También busca por SKU en todo el catálogo para capturar flexibles huérfanos.

Uso: python manage.py estructura_flexibles_subcategorias [--dry-run]
"""
from django.core.management.base import BaseCommand
from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import (
    normalize_measure_to_sku,
    FLEXIBLES_INNER_BRAID_NOMENCLATURE,
    FLEXIBLES_NIPPLES_NOMENCLATURE,
)


# SKUs de flexibles con extensión (reforzado con nipple/caño)
FLEXIBLES_CON_EXTENSION_SKUS = frozenset({"2X6EXT", "2X8EXT", "2X6EXT-REF", "2X8EXT-REF", "2.5X6EXT-REF"})


def _is_flexible_con_extension(sku):
    """Indica si el SKU corresponde a flexible con extensión (nipple)."""
    if not sku:
        return False
    su = (sku or "").strip().upper()
    return su in FLEXIBLES_CON_EXTENSION_SKUS


def _is_flexible_sku(sku):
    """Indica si el SKU corresponde a un flexible reforzado (normales o con extensión)."""
    if not sku:
        return False
    key = normalize_measure_to_sku(sku)
    su = (sku or "").strip().upper()
    return key in FLEXIBLES_INNER_BRAID_NOMENCLATURE or su in FLEXIBLES_NIPPLES_NOMENCLATURE or su in FLEXIBLES_CON_EXTENSION_SKUS


class Command(BaseCommand):
    help = "Estructura subcategorías Flexibles / Flexibles con extensión."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar qué se haría.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        cat_flex = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat_flex:
            cat_flex = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat_flex:
            self.stderr.write(self.style.ERROR("No existe la categoría Flexibles."))
            return

        # Crear subcategorías si no existen
        subcat_normales, created_n = Category.objects.get_or_create(
            slug="flexibles-normales",
            defaults={
                "name": "Flexibles estándar",
                "parent": cat_flex,
                "is_active": True,
            },
        )
        if not created_n:
            if subcat_normales.parent_id != cat_flex.id:
                if not dry_run:
                    subcat_normales.parent = cat_flex
                    subcat_normales.save(update_fields=["parent"])
                self.stdout.write("  Flexibles (normales): parent actualizado.")
            if not subcat_normales.is_active:
                if not dry_run:
                    subcat_normales.is_active = True
                    subcat_normales.save(update_fields=["is_active"])
        else:
            self.stdout.write(self.style.SUCCESS("  Creada subcategoría: Flexibles (flexibles-normales)"))

        subcat_ext, created_e = Category.objects.get_or_create(
            slug="flexibles-con-extension",
            defaults={
                "name": "Flexibles con extensión",
                "parent": cat_flex,
                "is_active": True,
            },
        )
        if not created_e:
            if subcat_ext.parent_id != cat_flex.id:
                if not dry_run:
                    subcat_ext.parent = cat_flex
                    subcat_ext.save(update_fields=["parent"])
            if not subcat_ext.is_active:
                if not dry_run:
                    subcat_ext.is_active = True
                    subcat_ext.save(update_fields=["is_active"])
        else:
            self.stdout.write(self.style.SUCCESS("  Creada subcategoría: Flexibles con extensión"))

        # Categorías donde pueden estar flexibles: flexibles, flexibles-reforzados, tubos-flexibles y descendientes
        flex_slugs = ("flexibles", "flexibles-reforzados", "tubos-flexibles")
        roots = Category.objects.filter(slug__in=flex_slugs, is_active=True)
        root_ids = list(roots.values_list("id", flat=True))
        # Descendientes directos (ej. flexibles-normales, flexibles-con-extension bajo flexibles)
        children = Category.objects.filter(parent_id__in=root_ids, is_active=True)
        child_ids = list(children.values_list("id", flat=True))
        flex_cat_ids = list(set(root_ids + child_ids + [subcat_normales.id, subcat_ext.id]))

        products_in_flex = list(
            Product.objects.filter(
                category_id__in=flex_cat_ids, is_active=True, deleted_at__isnull=True
            )
        )

        # También buscar flexibles por SKU en todo el catálogo (productos huérfanos en otras categorías)
        all_flexibles_by_sku = list(
            Product.objects.filter(is_active=True, deleted_at__isnull=True)
            .exclude(category_id__in=flex_cat_ids)
        )
        orphan_flexibles = [p for p in all_flexibles_by_sku if _is_flexible_sku(p.sku)]
        products_in_flex = list(set(products_in_flex + orphan_flexibles))

        to_ext = [p for p in products_in_flex if _is_flexible_con_extension(p.sku)]
        to_normales = [p for p in products_in_flex if p not in to_ext]

        if orphan_flexibles:
            samples = ", ".join(
                f"{p.sku}({getattr(p.category, 'slug', 'sin-cat')})" for p in orphan_flexibles[:5]
            )
            self.stdout.write(
                self.style.NOTICE(
                    f"  Encontrados {len(orphan_flexibles)} flexibles en otras categorías: {samples}"
                    + ("..." if len(orphan_flexibles) > 5 else "")
                )
            )

        if not dry_run:
            for p in to_ext:
                p.category = subcat_ext
                p.save(update_fields=["category"])
            for p in to_normales:
                p.category = subcat_normales
                p.save(update_fields=["category"])

        self.stdout.write(
            self.style.SUCCESS(
                f"  Flexibles con extensión: {len(to_ext)} productos ({', '.join(p.sku for p in to_ext)})"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  Flexibles (normales): {len(to_normales)} productos"
            )
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar cambios."))
