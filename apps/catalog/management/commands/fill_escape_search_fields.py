# -*- coding: utf-8 -*-
"""
Autofill seguro de campos para búsqueda por medidas (diametro_entrada, diametro_salida, largo_mm).

Solo actúa sobre productos incompletos: mismo conjunto que report_escape_search_gaps_detailed
(vía apps.catalog.escape_search_utils). Misma detección de direct fit, flexibles y "listo".

Reglas aplicadas a incompletos:
- Flexibles: medidas desde SKU (2X6, 2.5X8, 2X6EXT-REF, etc.) -> entrada, salida, largo_mm.
- Código en SKU (200/225/250/300) -> entrada, salida.
- Colas de escape: regla controlada 2 pulgadas -> entrada, salida.

Uso:
  python manage.py fill_escape_search_fields --dry-run   # solo ver qué se aplicaría
  python manage.py fill_escape_search_fields             # aplicar cambios
"""
from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.catalog.flexibles_nomenclature import parse_flexible_measure_from_sku
from apps.catalog.escape_search_utils import (
    get_products_queryset,
    is_direct_fit_product,
    is_flexible_product,
    is_ready_for_escape_search,
    is_incomplete_for_escape_search,
)
from .fill_catalog_diameters import (
    _s,
    _fill_diam_from_sku_code,
    DIAM_CODE_PATTERN,
    DIAM_CODE_MAP,
)

# Slug de categorías "cola de escape" -> regla 2 pulgadas
COLAS_SLUGS = ("colas-de-escape", "colas_de_escape")


def _is_cola(product):
    slug = (product.category.slug or "").strip().lower() if product.category_id else ""
    return slug in COLAS_SLUGS


def _fill_flexible_from_parsed(product, diam, largo_pulg, dry_run):
    """
    Rellena entrada, salida y largo_mm desde medidas ya parseadas (cubre 2X6EXT-REF, etc.).
    Solo rellena campos que están vacíos.
    """
    largo_mm = round(largo_pulg * 25.4)
    diam_dec = Decimal(str(round(diam, 2)))
    changed = False
    update_fields = []

    if product.diametro_entrada is None or product.diametro_entrada == 0:
        product.diametro_entrada = diam_dec
        changed = True
        update_fields.append("diametro_entrada")
    if product.diametro_salida is None or product.diametro_salida == 0:
        product.diametro_salida = diam_dec
        changed = True
        update_fields.append("diametro_salida")
    if getattr(product, "largo_mm", None) in (None, 0):
        product.largo_mm = largo_mm
        changed = True
        update_fields.append("largo_mm")

    if changed and update_fields and not dry_run:
        product.save(update_fields=update_fields)
    return changed, update_fields


def _fill_cola_2inch(product, dry_run):
    """Aplica regla: colas de escape = 2 pulgadas entrada y salida."""
    two = Decimal("2.00")
    changed = False
    update_fields = []
    if product.diametro_entrada is None or product.diametro_entrada == 0:
        product.diametro_entrada = two
        changed = True
        update_fields.append("diametro_entrada")
    if product.diametro_salida is None or product.diametro_salida == 0:
        product.diametro_salida = two
        changed = True
        update_fields.append("diametro_salida")
    if changed and update_fields and not dry_run:
        product.save(update_fields=update_fields)
    return changed, update_fields


class Command(BaseCommand):
    help = (
        "Rellena diametro_entrada, diametro_salida y largo_mm en productos incompletos "
        "(flexibles desde SKU, codigo 200/225/250/300, colas 2\"). Usa la misma clasificacion que los reportes. Incluye --dry-run."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar que se aplicaria, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo --dry-run: no se guardaran cambios."))

        # Mismo queryset y misma logica de clasificacion que report_escape_search_status y report_escape_search_gaps_detailed
        qs = get_products_queryset()

        total = 0
        excluded_direct_fit = 0
        excluded_ready = 0
        incompletos = []

        for p in qs:
            total += 1
            if is_direct_fit_product(p):
                excluded_direct_fit += 1
                continue
            if is_ready_for_escape_search(p):
                excluded_ready += 1
                continue
            incompletos.append(p)

        # Debug: debe coincidir con report_escape_search_gaps_detailed
        self.stdout.write("")
        self.stdout.write("===== FILL ESCAPE SEARCH FIELDS (debug) =====")
        self.stdout.write(f"Total productos recorridos: {total}")
        self.stdout.write(f"Excluidos por direct fit: {excluded_direct_fit}")
        self.stdout.write(f"Excluidos por listos: {excluded_ready}")
        self.stdout.write(f"Incompletos considerados: {len(incompletos)}")
        self.stdout.write("")

        stats = {"flexibles": 0, "codigo_sku": 0, "cola_2": 0, "skipped": 0, "no_rule": 0}
        log_filled = []
        log_skipped = []
        log_no_rule = []

        for p in incompletos:
            sku = _s(p.sku)
            name = (p.name or "")[:60]

            # 1) Flexible: desde SKU parseado (incluye 2X6, 2.5X8, 2X6EXT-REF, etc.)
            parsed = parse_flexible_measure_from_sku(p.sku)
            if parsed is not None:
                diam, largo_pulg = parsed
                changed, fields = _fill_flexible_from_parsed(p, diam, largo_pulg, dry_run)
                if changed:
                    stats["flexibles"] += 1
                    log_filled.append((p.sku, "flexible", f"diam {diam}\" largo {largo_pulg}\" -> {', '.join(fields)}"))
                else:
                    log_skipped.append((p.sku, "flexible (ya tenia datos)"))
                continue

            # 2) Codigo diametro en SKU (200/225/250/300)
            if DIAM_CODE_PATTERN.search(sku.upper()):
                changed = _fill_diam_from_sku_code(p) if not dry_run else False
                if dry_run:
                    m = DIAM_CODE_PATTERN.search(sku.upper())
                    if m and (p.diametro_entrada is None or p.diametro_salida is None):
                        diam_val = DIAM_CODE_MAP.get(m.group(1))
                        stats["codigo_sku"] += 1
                        log_filled.append((p.sku, "codigo_sku", f"-> {diam_val}\""))
                        changed = True
                if changed:
                    if not dry_run:
                        stats["codigo_sku"] += 1
                        log_filled.append((p.sku, "codigo_sku", "entrada/salida"))
                elif not dry_run:
                    log_skipped.append((p.sku, "codigo_sku (ya tenia diametros)"))
                continue

            # 3) Cola de escape -> 2 pulgadas
            if _is_cola(p):
                changed, fields = _fill_cola_2inch(p, dry_run)
                if changed:
                    stats["cola_2"] += 1
                    log_filled.append((p.sku, "cola_2pulg", "entrada/salida 2 pulg"))
                else:
                    log_skipped.append((p.sku, "cola (ya tenia diametros)"))
                continue

            stats["no_rule"] += 1
            log_no_rule.append((p.sku, name, p.category.slug if p.category_id else ""))

        # Resumen
        self.stdout.write("===== Resumen de reglas aplicadas =====")
        self.stdout.write(self.style.SUCCESS(f"Flexibles (desde SKU): {stats['flexibles']}"))
        self.stdout.write(self.style.SUCCESS(f"Codigo SKU (200/225/250/300): {stats['codigo_sku']}"))
        self.stdout.write(self.style.SUCCESS(f"Colas 2\": {stats['cola_2']}"))
        self.stdout.write(f"Omitidos (ya tenian dato): {stats['skipped']}")
        self.stdout.write(self.style.WARNING(f"Sin regla aplicable: {stats['no_rule']}"))
        self.stdout.write("")

        if log_filled:
            self.stdout.write("--- Cambios aplicados (o que se aplicarian con --dry-run) ---")
            for sku, rule, detail in log_filled[:50]:
                self.stdout.write(f"  [OK] {sku}  ({rule})  {detail}")
            if len(log_filled) > 50:
                self.stdout.write(f"  ... y {len(log_filled) - 50} mas.")
            self.stdout.write("")

        if log_no_rule and stats["no_rule"] <= 20:
            self.stdout.write("--- Sin regla (revision manual) ---")
            for sku, name, cat in log_no_rule:
                self.stdout.write(f"  {sku}  | {cat}  | {name}")
        elif log_no_rule:
            self.stdout.write(f"--- {stats['no_rule']} productos sin regla (revision manual). Ejemplos: ---")
            for sku, name, cat in log_no_rule[:15]:
                self.stdout.write(f"  {sku}  | {cat}  | {name}")

        if dry_run and (stats["flexibles"] or stats["codigo_sku"] or stats["cola_2"]):
            self.stdout.write("")
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar los cambios."))
