# -*- coding: utf-8 -*-
"""
Elimina duplicados de flexibles (misma medida, varios SKUs) y normaliza nombres.

- Agrupa por medida (diámetro x largo) y tipo (normal vs con extensión)
- Mantiene UN producto por medida, preferiendo SKU canónico (1.75X4, 2X6, 2X6EXT-REF, etc.)
- Soft-delete de los duplicados
- Actualiza nombre al formato: Flexible Reforzado 1,75" x 8"
- Asegura categoría correcta (flexibles-normales / flexibles-con-extension)

Uso: python manage.py dedupe_flexibles [--dry-run]
"""
from collections import defaultdict
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.models import Category, Product
from apps.catalog.flexibles_nomenclature import (
    normalize_measure_to_sku,
    parse_flexible_measure_from_sku,
    FLEXIBLES_INNER_BRAID_NOMENCLATURE,
    FLEXIBLES_NIPPLES_NOMENCLATURE,
)

from apps.catalog.management.commands.sync_flexibles_precios import (
    FLEXIBLES_REFORZADOS,
    FLEXIBLES_CON_EXTENSION,
)


def _format_measure(val):
    if val is None:
        return ""
    v = float(val)
    if v == int(v):
        return str(int(v))
    return str(v).replace(".", ",")


def _build_name(parsed, con_extension=False):
    if not parsed:
        return None
    diam, largo = parsed
    d_str = _format_measure(diam)
    l_str = _format_measure(largo)
    base = "Flexible Reforzado"
    if con_extension:
        base += " con extensión"
    return f'{base} {d_str}" x {l_str}"'


def _canonical_sku_rank(p, is_extension, reforzados_keys, extension_keys):
    """Menor = mejor. Preferir SKU canonico (1.75X4, 2X6) sobre variantes (1,75-X-4, 2-X-6)."""
    sku = p.sku or ""
    sku_upper = sku.strip().upper()
    key = normalize_measure_to_sku(sku)
    if is_extension:
        if sku_upper in extension_keys:
            return (0, extension_keys.index(sku_upper))
        if "EXT-REF" in sku_upper:
            return (1, 0)
        return (2, 0)
    if key in reforzados_keys:
        idx = reforzados_keys.index(key)
        if sku_upper == reforzados_keys[idx]:
            return (0, idx)
        return (1, idx)
    return (2, 999)


class Command(BaseCommand):
    help = "Elimina duplicados de flexibles y normaliza nombres al formato requerido."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo mostrar cambios sin aplicar.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se aplicaran cambios."))

        cat_flex = Category.objects.filter(slug="flexibles", is_active=True).first()
        if not cat_flex:
            cat_flex = Category.objects.filter(name__iexact="Flexibles", is_active=True).first()
        if not cat_flex:
            self.stderr.write(self.style.ERROR("No existe la categoria Flexibles."))
            return

        cat_normales = Category.objects.filter(slug="flexibles-normales", is_active=True).first()
        cat_ext = Category.objects.filter(slug="flexibles-con-extension", is_active=True).first()
        if not cat_normales or not cat_ext:
            self.stderr.write(self.style.ERROR("Faltan categorias flexibles-normales o flexibles-con-extension."))
            return

        cat_ids = [cat_flex.id] + list(
            Category.objects.filter(parent=cat_flex, is_active=True).values_list("id", flat=True)
        )
        products = list(
            Product._base_manager.filter(category_id__in=cat_ids)
            .select_related("category")
            .order_by("sku")
        )

        reforzados_keys = list(FLEXIBLES_REFORZADOS.keys())
        extension_keys = list(FLEXIBLES_CON_EXTENSION.keys())

        # Agrupar por (is_extension, diam, largo)
        groups = defaultdict(list)
        for p in products:
            parsed = parse_flexible_measure_from_sku(p.sku)
            if not parsed:
                continue
            is_ext = "EXT" in (p.sku or "").upper()
            key = (is_ext, parsed[0], parsed[1])
            groups[key].append(p)

        soft_deleted = 0
        updated = 0

        for (is_ext, diam, largo), prods in sorted(groups.items(), key=lambda x: (not x[0][0], x[0][1], x[0][2])):
            if len(prods) == 1:
                prod = prods[0]
                new_name = _build_name((diam, largo), is_ext)
                if not new_name:
                    continue
                new_name = new_name[:255]
                cat_ok = cat_ext if is_ext else cat_normales
                needs_save = []
                if prod.name != new_name:
                    prod.name = new_name
                    needs_save.append("name")
                if prod.category_id != cat_ok.id:
                    prod.category = cat_ok
                    needs_save.append("category")
                if prod.deleted_at:
                    prod.deleted_at = None
                    prod.is_active = True
                    prod.is_publishable = True
                    needs_save.extend(["deleted_at", "is_active", "is_publishable"])
                if needs_save and not dry_run:
                    prod.save(update_fields=list(dict.fromkeys(needs_save)))
                if needs_save:
                    updated += 1
                    self.stdout.write(f"  [unico] {prod.sku}: nombre/cat actualizados")
                continue

            prods_sorted = sorted(
                prods,
                key=lambda p: _canonical_sku_rank(p, is_ext, reforzados_keys, extension_keys),
            )
            keeper = prods_sorted[0]
            duplicates = prods_sorted[1:]

            price_map = FLEXIBLES_CON_EXTENSION if is_ext else FLEXIBLES_REFORZADOS
            canonical_sku = None
            for k in (extension_keys if is_ext else reforzados_keys):
                if parse_flexible_measure_from_sku(k) == (diam, largo):
                    canonical_sku = k
                    break

            new_name = _build_name((diam, largo), is_ext)
            if not new_name:
                continue
            new_name = new_name[:255]
            cat_ok = cat_ext if is_ext else cat_normales

            for dup in duplicates:
                self.stdout.write(f"  SOFT-DELETE: {dup.sku} (duplicado de {keeper.sku})")
                if not dry_run:
                    dup.deleted_at = timezone.now()
                    dup.is_active = False
                    dup.save(update_fields=["deleted_at", "is_active"])
                soft_deleted += 1

            needs_save = []
            if keeper.name != new_name:
                keeper.name = new_name
                needs_save.append("name")
            if keeper.category_id != cat_ok.id:
                keeper.category = cat_ok
                needs_save.append("category")
            price_val = price_map.get(canonical_sku) or price_map.get(normalize_measure_to_sku(keeper.sku))
            if price_val and keeper.price != Decimal(str(price_val)):
                keeper.price = Decimal(str(price_val))
                needs_save.append("price")
            if keeper.deleted_at:
                keeper.deleted_at = None
                keeper.is_active = True
                keeper.is_publishable = True
                needs_save.extend(["deleted_at", "is_active", "is_publishable"])
            if needs_save and not dry_run:
                keeper.save(update_fields=list(dict.fromkeys(needs_save)))
            updated += 1
            self.stdout.write(f"  MANTENER: {keeper.sku} -> \"{new_name}\" | soft-delete {len(duplicates)} duplicados")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {soft_deleted} duplicados soft-delete, {updated} productos actualizados."
                + (" (dry-run)" if dry_run else "")
            )
        )
        if dry_run:
            self.stdout.write(self.style.NOTICE("Ejecuta sin --dry-run para aplicar cambios."))
