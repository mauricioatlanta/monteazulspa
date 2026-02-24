# -*- coding: utf-8 -*-
"""
Reclasifica productos de escape MonteAzul por prefijo de SKU:
- LT* → Resonadores
- DW*, DWR*, LTM* → Silenciadores Alto Flujo

Actualiza Product.category y Product.name. No modifica slugs existentes.
Crea categorías Resonadores y Silenciadores Alto Flujo si no existen.

Uso:
    python manage.py reclassify_monteazul_exhaust              # dry-run
    python manage.py reclassify_monteazul_exhaust --apply
    python manage.py reclassify_monteazul_exhaust --only-prefix LT
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import Category, Product


# Categorías raíz (parent=None)
CAT_RESONADORES = {"name": "Resonadores", "slug": "resonadores"}
CAT_ALTO_FLUJO = {"name": "Silenciadores Alto Flujo", "slug": "silenciadores-alto-flujo"}


def _get_target_category(sku):
    """
    Devuelve (slug_categoria, tipo) según prefijo del SKU.
    tipo: "resonador" | "alto_flujo" | None (no aplica).
    """
    if not sku or not isinstance(sku, str):
        return None, None
    u = sku.strip().upper()
    if u.startswith("LT") and not u.startswith("LTM"):
        return CAT_RESONADORES["slug"], "resonador"
    if u.startswith("DW") or u.startswith("DWR") or u.startswith("LTM"):
        return CAT_ALTO_FLUJO["slug"], "alto_flujo"
    return None, None


def _build_resonator_name(product):
    """Nombre estándar para resonador. Sin campos shape/body/overall → mínimo 'Resonador {sku}'."""
    sku = (product.sku or "").strip()
    return f"Resonador {sku}"[:255]


def _build_alto_flujo_name(product):
    """Nombre estándar para silenciador alto flujo. Incluye material si existe."""
    sku = (product.sku or "").strip()
    material_label = ""
    if product.material:
        material_label = f" ({product.get_material_display()})"
    return f"Silenciador Alto Flujo {sku}{material_label}"[:255]


def _should_rename(product, new_name, target_slug):
    """True si conviene actualizar el nombre (genérico o distinto al nuevo estándar)."""
    current = (product.name or "").strip()
    if not current or current == new_name:
        return False
    # Renombrar si está en categoría equivocada o nombre muy genérico
    if target_slug == CAT_RESONADORES["slug"]:
        if not current.lower().startswith("resonador"):
            return True
    if target_slug == CAT_ALTO_FLUJO["slug"]:
        if "silenciador alto flujo" not in current.lower():
            return True
    return False


class Command(BaseCommand):
    help = "Reclasifica productos LT/DW/DWR/LTM a Resonadores o Silenciadores Alto Flujo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            dest="apply",
            help="Aplicar cambios en BD. Por defecto es dry-run.",
        )
        parser.add_argument(
            "--only-prefix",
            type=str,
            metavar="PREFIX",
            choices=["LT", "DW", "DWR", "LTM"],
            help="Procesar solo productos con este prefijo.",
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        only_prefix = (options.get("only_prefix") or "").strip().upper()
        mode = "apply" if apply else "dry-run"
        self.stdout.write(self.style.NOTICE(f"[{mode}] Reclasificación MonteAzul exhaust"))

        # 1) Asegurar categorías (raíz)
        cat_resonadores = self._ensure_category(CAT_RESONADORES, apply)
        cat_alto_flujo = self._ensure_category(CAT_ALTO_FLUJO, apply)
        # En dry-run usar categoría existente o nombre del spec para salida
        if not cat_resonadores:
            cat_resonadores = Category.objects.filter(slug=CAT_RESONADORES["slug"]).first()
        if not cat_alto_flujo:
            cat_alto_flujo = Category.objects.filter(slug=CAT_ALTO_FLUJO["slug"]).first()
        if not apply and not Category.objects.filter(slug__in=[CAT_RESONADORES["slug"], CAT_ALTO_FLUJO["slug"]]).exists():
            self.stdout.write(self.style.WARNING("Ejecuta con --apply para crear categorías si faltan."))

        # 2) Productos candidatos por prefijo
        sku_prefixes = ["LT", "DW", "DWR", "LTM"]
        if only_prefix:
            # LT solo para resonadores; DW/DWR/LTM para alto flujo
            if only_prefix == "LT":
                sku_prefixes = ["LT"]
            else:
                sku_prefixes = [only_prefix]

        # Query: SKU que empiece con alguno de los prefijos (LT pero no LTM para no duplicar)
        from django.db.models import Q
        q = Q()
        for p in sku_prefixes:
            q = q | Q(sku__istartswith=p)
        # Excluir LTM cuando estamos solo con LT (LT* = resonadores, no LTM*)
        if "LT" in sku_prefixes and "LTM" not in sku_prefixes:
            q = q & ~Q(sku__istartswith="LTM")
        products = list(
            Product.objects.filter(q, deleted_at__isnull=True)
            .select_related("category")
            .order_by("sku")
        )

        # Filtrar por regla exacta: LT (no LTM) -> resonador; DW/DWR/LTM -> alto flujo
        to_resonadores = []
        to_alto_flujo = []
        for p in products:
            target_slug, tipo = _get_target_category(p.sku)
            if not target_slug:
                continue
            if only_prefix:
                if only_prefix == "LT" and tipo != "resonador":
                    continue
                if only_prefix in ("DW", "DWR", "LTM") and tipo != "alto_flujo":
                    continue
            if tipo == "resonador":
                to_resonadores.append(p)
            else:
                to_alto_flujo.append(p)

        # 3) Actualizar
        updated_cat = 0
        updated_name = 0
        for p in to_resonadores + to_alto_flujo:
            target_slug, tipo = _get_target_category(p.sku)
            if target_slug == CAT_RESONADORES["slug"]:
                new_cat = cat_resonadores
                new_name = _build_resonator_name(p)
                new_cat_name = (cat_resonadores.name if cat_resonadores else CAT_RESONADORES["name"])
            else:
                new_cat = cat_alto_flujo
                new_name = _build_alto_flujo_name(p)
                new_cat_name = (cat_alto_flujo.name if cat_alto_flujo else CAT_ALTO_FLUJO["name"])

            old_cat = p.category.name if p.category_id else ""
            old_name = (p.name or "").strip()
            change_cat = old_cat != new_cat_name and new_cat is not None
            change_name = _should_rename(p, new_name, target_slug)

            if change_cat or change_name:
                self.stdout.write(
                    f"  {p.sku}  {old_cat} -> {new_cat_name}  |  "
                    f"{old_name[:40]} -> {new_name[:40]}"
                )
                if apply and new_cat:
                    if change_cat:
                        p.category = new_cat
                        updated_cat += 1
                    if change_name:
                        p.name = new_name
                        updated_name += 1
                    if change_cat or change_name:
                        fields = []
                        if change_cat:
                            fields.append("category")
                        if change_name:
                            fields.append("name")
                        if fields:
                            p.save(update_fields=fields)

        # 4) Validación: conteos y top 5
        self._print_summary(to_resonadores, to_alto_flujo, apply, updated_cat, updated_name)

        if not apply:
            self.stdout.write(self.style.WARNING("Dry-run. Usa --apply para guardar cambios."))

    def _ensure_category(self, spec, apply):
        """Crea o obtiene categoría con name/slug y parent=None."""
        slug = spec["slug"]
        name = spec["name"]
        cat = Category.objects.filter(slug=slug).first()
        if cat:
            if cat.parent_id is not None and apply:
                cat.parent = None
                cat.save(update_fields=["parent"])
            if cat.name != name and apply:
                cat.name = name
                cat.save(update_fields=["name"])
            return cat
        if apply:
            cat = Category.objects.create(
                name=name,
                slug=slug,
                parent=None,
                is_active=True,
            )
            self.stdout.write(self.style.SUCCESS(f"  Categoría creada: {name} ({slug})"))
            return cat
        return None

    def _print_summary(self, to_resonadores, to_alto_flujo, apply, updated_cat, updated_name):
        """Cuántos LT → Resonadores, cuántos DW/DWR/LTM → Alto Flujo; top 5 por grupo."""
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("--- Resumen ---"))
        self.stdout.write(f"  LT* -> Resonadores: {len(to_resonadores)} productos")
        for p in to_resonadores[:5]:
            self.stdout.write(f"    - {p.sku}  {p.name[:50] if p.name else ''}")
        if len(to_resonadores) > 5:
            self.stdout.write(f"    ... y {len(to_resonadores) - 5} más")
        self.stdout.write(f"  DW*/DWR*/LTM* -> Silenciadores Alto Flujo: {len(to_alto_flujo)} productos")
        for p in to_alto_flujo[:5]:
            self.stdout.write(f"    - {p.sku}  {p.name[:50] if p.name else ''}")
        if len(to_alto_flujo) > 5:
            self.stdout.write(f"    ... y {len(to_alto_flujo) - 5} más")
        if apply:
            self.stdout.write(f"  Categorías actualizadas: {updated_cat}  |  Nombres actualizados: {updated_name}")
