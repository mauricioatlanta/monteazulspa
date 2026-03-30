# -*- coding: utf-8 -*-
"""
Lógica compartida para clasificación de productos respecto a búsqueda por medidas (escape).

Usado por:
- report_escape_search_status
- report_escape_search_gaps_detailed
- fill_escape_search_fields

Todos deben usar el mismo queryset base y las mismas funciones para que los números coincidan.
"""
from apps.catalog.models import Product
from apps.catalog.flexibles_nomenclature import parse_flexible_measure_from_sku


# Categorías de flexibles: para ellos exige también largo_mm para estar "listos"
FLEXIBLES_SLUGS = (
    "flexibles",
    "flexibles-reforzados",
    "flexibles-normales",
    "flexibles-con-extension",
)


def get_products_queryset():
    """
    Queryset base para todos los comandos de reporte/autofill.
    Mismo universo = mismos números entre report_escape_search_gaps_detailed y fill_escape_search_fields.
    """
    return (
        Product.objects.filter(deleted_at__isnull=True)
        .select_related("category")
        .order_by("category__name", "sku")
    )


def is_direct_fit_product(product):
    """
    Productos que se buscan por vehículo (direct fit), no por medidas.
    
    Criterio principal: tiene compatibilidad específica con modelo (model no nulo).
    Criterio secundario (apoyo): SKU contiene CLF o nombre contiene DIRECT.
    """
    # Criterio principal: compatibilidad específica por modelo
    if hasattr(product, 'compatibilities'):
        # Si ya está prefetched, usar eso
        try:
            compatibilities = product.compatibilities.all()
            has_model_specific = any(
                c.model_id is not None and c.is_active
                for c in compatibilities
            )
            if has_model_specific:
                return True
        except Exception:
            pass
    
    # Si no hay compatibilities prefetched, hacer query directo
    try:
        from apps.catalog.models import ProductCompatibility
        has_model_specific = ProductCompatibility.objects.filter(
            product=product,
            model__isnull=False,
            is_active=True
        ).exists()
        if has_model_specific:
            return True
    except Exception:
        pass
    
    # Criterio secundario: heurística por SKU/nombre
    sku = (product.sku or "").upper()
    name = (product.name or "").upper()
    return "CLF" in sku or "DIRECT" in name


def is_flexible_product(product):
    """Flexible por categoría o por SKU (formato diámetro x largo)."""
    cat_slug = (product.category.slug or "") if product.category_id else ""
    if cat_slug in FLEXIBLES_SLUGS:
        return True
    return parse_flexible_measure_from_sku(product.sku) is not None


def is_ready_for_escape_search(product):
    """
    Listo para búsqueda por medidas según tipo:
    - Direct fit: no aplica (se clasifica aparte).
    - Flexibles: requieren entrada, salida y largo_mm.
    - Resto (colas, silenciadores, resonadores, etc.): entrada y salida suficientes.
    """
    entrada = product.diametro_entrada
    salida = product.diametro_salida
    largo = product.largo_mm

    if not entrada or not salida:
        return False
    if is_flexible_product(product):
        return bool(largo)
    return True


def is_incomplete_for_escape_search(product):
    """
    Incompleto = no es direct fit y aún no está listo para búsqueda por medidas.
    Es el mismo conjunto que report_escape_search_gaps_detailed y el que fill_escape_search_fields debe procesar.
    """
    if is_direct_fit_product(product):
        return False
    return not is_ready_for_escape_search(product)
