from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When

from apps.catalog.models import Product, VehicleBrand, VehicleModel, VehicleEngine
from apps.catalog.services.technical_rules import allowed_diameters, year_to_euro, _norm_fuel


def _normalize_fuel_from_engine(engine: Optional[VehicleEngine]) -> str:
    """Combustible normalizado para filtrar Product.combustible (BENCINA/DIESEL)."""
    if not engine or not engine.fuel_type:
        return ""
    return _norm_fuel(engine.fuel_type) or ""


def apply_engine_filter(
    qs: QuerySet[Product],
    cc: Optional[int] = None,
    fuel: Optional[str] = None,
    year: Optional[int] = None,
) -> QuerySet[Product]:
    """
    Filtro técnico reutilizable por motor sobre un queryset de productos.

    - No rompe si faltan datos (cc/fuel/year pueden venir vacíos).
    - Siempre intenta mejorar el queryset sin dejarlo vacío artificialmente.
    """
    if qs is None:
        return qs

    fuel_norm = _norm_fuel(fuel)

    # 1) Filtro "suave" por combustible: prioriza coincidencias, pero permite nulos.
    if fuel_norm:
        qs = qs.filter(Q(combustible=fuel_norm) | Q(combustible__isnull=True))

    # 2) Filtro por diámetro sugerido según cilindrada/combustible.
    if cc:
        diameters = allowed_diameters(cc, fuel_norm)
        if diameters:
            qs = qs.filter(
                Q(diametro_entrada__in=diameters) | Q(diametro_entrada__isnull=True)
            )

    # 3) Filtro por norma Euro derivada del año.
    if year:
        euro = year_to_euro(year)
        if euro:
            qs = qs.filter(Q(euro_norm=euro) | Q(euro_norm__isnull=True))

    return qs


def get_vehicle_suggested_products(
    *,
    brand: VehicleBrand,
    model: VehicleModel,
    year: int,
    engine: Optional[VehicleEngine] = None,
    exclude_product_ids: Optional[Sequence[int]] = None,
    limit: int = 32,
) -> QuerySet[Product]:
    """
    Devuelve productos sugeridos técnicamente (universales) para un vehículo.

    No depende de ProductCompatibility; usa reglas por año/norma Euro,
    combustible y cilindrada/diámetros permitidos.
    """
    exclude_ids: Set[int] = set(int(x) for x in (exclude_product_ids or []) if x)

    euro = year_to_euro(year)
    fuel = _normalize_fuel_from_engine(engine)
    cc = engine.displacement_cc if engine else None
    diameters = allowed_diameters(cc, fuel) if cc else []

    base_qs = Product.objects.filter(
        is_publishable=True,
        is_active=True,
        deleted_at__isnull=True,
    ).select_related("category")

    if exclude_ids:
        base_qs = base_qs.exclude(id__in=exclude_ids)

    # 1) Catalíticos universales TWG: norma Euro (bencina) o diesel, combustible, rango cc, diámetro
    # fuel ya viene normalizado por _normalize_fuel_from_engine → BENCINA/DIESEL
    fuel_product = (fuel or "").strip().upper()
    if fuel_product == "DIESEL":
        twc_slugs = ("cataliticos-twc", "cataliticos-twc-diesel")
    else:
        twc_slugs = ("cataliticos-twc", "cataliticos-twc-euro3", "cataliticos-twc-euro4", "cataliticos-twc-euro5")
    twc_filters = Q(category__slug__in=twc_slugs)
    if fuel_product:
        # Incluir productos con combustible exacto o sin combustible cargado (sugerir para confirmar)
        twc_filters &= (Q(combustible=fuel_product) | Q(combustible__isnull=True))
    if euro and fuel_product != "DIESEL":
        # Bencina: sugerir cualquier TWG Euro 3/4/5 (un Euro 5 puede usar catalítico Euro 3/4; confirmar con asesor)
        euro_values = ("EURO3", "EURO4", "EURO5")
        twc_filters &= (Q(euro_norm__in=euro_values) | Q(euro_norm__isnull=True))
    if cc is not None:
        twc_filters &= (
            (Q(recommended_cc_min__isnull=True) | Q(recommended_cc_min__lte=cc))
            & (Q(recommended_cc_max__isnull=True) | Q(recommended_cc_max__gte=cc))
        )
    if diameters:
        # Incluir catalíticos con diámetro en rango o sin diámetro cargado (sugerir para confirmar)
        twc_filters &= (Q(diametro_entrada__in=diameters) | Q(diametro_entrada__isnull=True))
    twg_qs = base_qs.filter(twc_filters)

    # 2) Flexibles por diámetro (normales, con extensión y reforzados; alineado con FLEXIBLES_SLUGS del modelo)
    flex_slugs = ("flexibles", "flexibles-reforzados", "flexibles-normales", "flexibles-con-extension")
    flex_filters = Q(category__slug__in=flex_slugs)
    if diameters:
        flex_filters &= Q(diametro_entrada__in=diameters)
    flex_qs = base_qs.filter(flex_filters)

    # Orden: flexibles con EXT en SKU primero, luego por nombre (Q no sirve en order_by → Case/When)
    flex_qs = flex_qs.annotate(
        ext_priority=Case(
            When(sku__icontains="EXT", then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by("-ext_priority", "name")

    # 3) Silenciadores, resonadores y colas/puntas (universales; sugerir para confirmar medida)
    other_slugs = (
        "resonadores",
        "silenciadores-alto-flujo",
        "silenciadores-de-alto-flujo",
        "silenciadores",
        "colas-de-escape",
        "colas_de_escape",
    )
    other_qs = base_qs.filter(category__slug__in=other_slugs).order_by("name")

    # Unión de resultados, limitada: catalíticos → flexibles → silenciadores/resonadores/colas
    ids: List[int] = []
    for qs in (twg_qs.order_by("sku"), flex_qs, other_qs):
        for pid in qs.values_list("id", flat=True):
            if pid in ids:
                continue
            ids.append(pid)
            if len(ids) >= limit:
                break
        if len(ids) >= limit:
            break

    # Fallback: si no hubo coincidencias (p. ej. motor sin fuel/cc, datos incompletos), sugerir TWG + flexibles + otros
    if not ids:
        fallback_twc = base_qs.filter(category__slug__in=twc_slugs).order_by("sku")
        fallback_flex = base_qs.filter(category__slug__in=flex_slugs)
        fallback_flex = fallback_flex.annotate(
            ext_priority=Case(
                When(sku__icontains="EXT", then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by("-ext_priority", "name")
        fallback_other = base_qs.filter(category__slug__in=other_slugs).order_by("name")
        for qs in (fallback_twc, fallback_flex, fallback_other):
            for pid in qs.values_list("id", flat=True):
                if pid in ids:
                    continue
                ids.append(pid)
                if len(ids) >= limit:
                    break
            if len(ids) >= limit:
                break

    # Último recurso: si sigue vacío (p. ej. categorías sin productos), sugerir cualquier producto publicable
    if not ids:
        for pid in base_qs.order_by("name").values_list("id", flat=True)[:limit]:
            ids.append(pid)
            if len(ids) >= limit:
                break

    if not ids:
        return Product.objects.none()

    # Mantener orden por la lista de ids (tabla explícita para evitar "ambiguous column name: id" con JOINs)
    preserved = {pid: idx for idx, pid in enumerate(ids)}
    table = Product._meta.db_table
    case_sql = "CASE " + table + ".id " + " ".join(f"WHEN {pid} THEN {idx}" for pid, idx in preserved.items()) + " END"
    return (
        Product.objects.filter(id__in=ids)
        .select_related("category")
        .prefetch_related("images")
        .extra(select={"_order": case_sql})
        .order_by("_order")
    )


def get_vehicle_suggested_products_v2(
    *,
    brand: VehicleBrand,
    model: VehicleModel,
    year: int,
    engine: Optional[VehicleEngine] = None,
    exclude_product_ids: Optional[Sequence[int]] = None,
    limit: int = 32,
) -> QuerySet[Product]:
    """
    Versión mejorada de sugerencias técnicas por vehículo.

    - Usa cilindrada + combustible para restringir diámetros.
    - Aplica rango de normas Euro según año del vehículo.
    - Mantiene filtro estricto de diámetro para flexibles, incluso en fallback.
    """
    exclude_ids: Set[int] = set(int(x) for x in (exclude_product_ids or []) if x)

    euro = year_to_euro(year)
    fuel = _normalize_fuel_from_engine(engine)
    cc = engine.displacement_cc if engine else None

    # Diámetros base según cilindrada; si no hay cc, usar rango conservador
    # para no sugerir 2.5" o 3" por defecto en vehículos livianos.
    if cc:
        diameters = allowed_diameters(cc, fuel)
    else:
        fuel_norm = (fuel or "").strip().upper()
        if fuel_norm == "DIESEL":
            diameters = [2.0, 2.25]
        else:
            # Bencina o desconocido: asumir auto liviano
            diameters = [1.75, 2.0, 2.25]

    base_qs = Product.objects.filter(
        is_publishable=True,
        is_active=True,
        deleted_at__isnull=True,
    ).select_related("category")

    if exclude_ids:
        base_qs = base_qs.exclude(id__in=exclude_ids)

    # Regla de normas Euro por año (rango, no un solo valor)
    allowed_euro_values: Optional[Sequence[str]] = None
    if year is not None:
        try:
            y = int(year)
            if y >= 2015:
                allowed_euro_values = ("EURO5",)
            elif y >= 2010:
                allowed_euro_values = ("EURO4", "EURO5")
            else:
                allowed_euro_values = ("EURO3", "EURO4")
        except (TypeError, ValueError):
            allowed_euro_values = None

    # 1) Catalíticos universales TWG con filtros técnicos estrictos
    fuel_product = (fuel or "").strip().upper()
    if fuel_product == "DIESEL":
        twc_slugs = ("cataliticos-twc", "cataliticos-twc-diesel")
    else:
        twc_slugs = (
            "cataliticos-twc",
            "cataliticos-twc-euro3",
            "cataliticos-twc-euro4",
            "cataliticos-twc-euro5",
        )

    twc_filters = Q(category__slug__in=twc_slugs)

    if fuel_product:
        twc_filters &= (Q(combustible=fuel_product) | Q(combustible__isnull=True))

    if allowed_euro_values:
        # Restringir explícitamente a rangos válidos por año; aún se aceptan nulos.
        twc_filters &= (Q(euro_norm__in=allowed_euro_values) | Q(euro_norm__isnull=True))

    if cc is not None:
        twc_filters &= (
            (Q(recommended_cc_min__isnull=True) | Q(recommended_cc_min__lte=cc))
            & (Q(recommended_cc_max__isnull=True) | Q(recommended_cc_max__gte=cc))
        )

    if diameters:
        twc_filters &= (
            Q(diametro_entrada__in=diameters)
            | Q(diametro_salida__in=diameters)
            | (Q(diametro_entrada__isnull=True) & Q(diametro_salida__isnull=True))
        )

    twg_qs = base_qs.filter(twc_filters)

    # 2) Flexibles: siempre restringidos por diámetro permitido
    flex_slugs = ("flexibles", "flexibles-reforzados", "flexibles-normales", "flexibles-con-extension")
    flex_filters = Q(category__slug__in=flex_slugs)
    if diameters:
        flex_filters &= (
            Q(diametro_entrada__in=diameters)
            | Q(diametro_salida__in=diameters)
        )
    flex_qs = base_qs.filter(flex_filters)

    flex_qs = flex_qs.annotate(
        ext_priority=Case(
            When(sku__icontains="EXT", then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    ).order_by("-ext_priority", "name")

    # 3) Silenciadores, resonadores y colas universales
    other_slugs = (
        "resonadores",
        "silenciadores-alto-flujo",
        "silenciadores-de-alto-flujo",
        "silenciadores",
        "colas-de-escape",
        "colas_de_escape",
    )
    other_qs = base_qs.filter(category__slug__in=other_slugs).order_by("name")

    # Unión priorizada de resultados
    ids: List[int] = []
    for qs in (twg_qs.order_by("sku"), flex_qs, other_qs):
        for pid in qs.values_list("id", flat=True):
            if pid in ids:
                continue
            ids.append(pid)
            if len(ids) >= limit:
                break
        if len(ids) >= limit:
            break

    # Fallback: mantener filtros de diámetro siempre que haya cilindrada conocida
    if not ids:
        fallback_twc_filters = Q(category__slug__in=twc_slugs)
        if fuel_product:
            fallback_twc_filters &= (Q(combustible=fuel_product) | Q(combustible__isnull=True))
        if allowed_euro_values:
            fallback_twc_filters &= (Q(euro_norm__in=allowed_euro_values) | Q(euro_norm__isnull=True))
        if cc is not None and diameters:
            fallback_twc_filters &= (
                Q(diametro_entrada__in=diameters)
                | Q(diametro_salida__in=diameters)
                | (Q(diametro_entrada__isnull=True) & Q(diametro_salida__isnull=True))
            )

        fallback_twc = base_qs.filter(fallback_twc_filters).order_by("sku")

        fallback_flex_filters = Q(category__slug__in=flex_slugs)
        if diameters:
            fallback_flex_filters &= (
                Q(diametro_entrada__in=diameters)
                | Q(diametro_salida__in=diameters)
            )
        fallback_flex = base_qs.filter(fallback_flex_filters)
        fallback_flex = fallback_flex.annotate(
            ext_priority=Case(
                When(sku__icontains="EXT", then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        ).order_by("-ext_priority", "name")

        fallback_other = base_qs.filter(category__slug__in=other_slugs).order_by("name")

        for qs in (fallback_twc, fallback_flex, fallback_other):
            for pid in qs.values_list("id", flat=True):
                if pid in ids:
                    continue
                ids.append(pid)
                if len(ids) >= limit:
                    break
            if len(ids) >= limit:
                break

    # Último recurso extremadamente amplio (no recomendado, pero evita lista vacía total)
    if not ids:
        for pid in base_qs.order_by("name").values_list("id", flat=True)[:limit]:
            ids.append(pid)
            if len(ids) >= limit:
                break

    if not ids:
        return Product.objects.none()

    preserved = {pid: idx for idx, pid in enumerate(ids)}
    table = Product._meta.db_table
    case_sql = (
        "CASE "
        + table
        + ".id "
        + " ".join(f"WHEN {pid} THEN {idx}" for pid, idx in preserved.items())
        + " END"
    )
    return (
        Product.objects.filter(id__in=ids)
        .select_related("category")
        .prefetch_related("images")
        .extra(select={"_order": case_sql})
        .order_by("_order")
    )


__all__ = ["get_vehicle_suggested_products", "get_vehicle_suggested_products_v2", "apply_engine_filter"]

