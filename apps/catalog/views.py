from collections import OrderedDict

from django.conf import settings
from django.db import models
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.db.models import Q, Count, Prefetch, Case, When, IntegerField, QuerySet
from django.views.decorators.http import require_GET
from .models import Product, Category, ProductCompatibility, ProductImage, ProductViewStat, SearchLog
from apps.catalog.utils.engine_query_parser import parse_engine_query
from apps.catalog.services.vehicle_recommendation_rules import apply_engine_filter

# Import interno para evitar circular - review_submit usa apps.reviews
from .templatetags.catalog_filters import format_pesos_cl

# Año → slug subcategoría Euro (catalíticos universales TWG)
# Euro 3: hasta 2005, Euro 4: 2006-2010, Euro 5: 2011+
def _year_to_euro_cat_slug(year):
    try:
        y = int(year)
        if y <= 2005:
            return "cataliticos-twc-euro3"
        if y <= 2010:
            return "cataliticos-twc-euro4"
        return "cataliticos-twc-euro5"
    except (TypeError, ValueError):
        return None


def _wizard_year_to_euro(year):
    """Año → norma Euro para el asistente. Regla: >=2011 solo Euro 5 (evitar Check Engine)."""
    try:
        y = int(year)
        if y <= 2005:
            return "EURO3"
        if y <= 2010:
            return "EURO4"
        return "EURO5"
    except (TypeError, ValueError):
        return None


def _wizard_resolve_category_slugs(fuel, anno, tipo):
    """
    Dado combustible (bencina|diesel), año y tipo (twg|clf), devuelve lista de slugs
    de categoría para filtrar. Si anno >= 2011 y tipo=twg, solo Euro 5 (no mostrar Euro 3).
    """
    fuel = (fuel or "").strip().lower()
    tipo = (tipo or "").strip().lower()
    euro = _wizard_year_to_euro(anno) if anno else None

    if tipo == "clf":
        return ["cataliticos-clf", "cataliticos-ensamble-directo"]

    # TWG
    if fuel == "diesel":
        return ["cataliticos-twc-diesel"]
    # Bencina
    if euro == "EURO3":
        return ["cataliticos-twc-euro3"]
    if euro == "EURO4":
        return ["cataliticos-twc-euro4"]
    if euro == "EURO5":
        return ["cataliticos-twc-euro5"]
    # año no válido: mostrar todos los Euro TWG bencina
    return ["cataliticos-twc-euro3", "cataliticos-twc-euro4", "cataliticos-twc-euro5"]


def _get_descendant_category_ids(category_id):
    """Devuelve el id de la categoría y todos sus descendientes (recursivo)."""
    ids = [category_id]
    children = list(
        Category.objects.filter(parent_id=category_id, is_active=True).values_list("id", flat=True)
    )
    for cid in children:
        ids.extend(_get_descendant_category_ids(cid))
    return ids


# Ambas slugs son la misma línea de producto (Ensamble Directo CLF); al filtrar por una se muestran ambas.
CLF_ENSAMBLE_SLUGS = ("cataliticos-clf", "cataliticos-ensamble-directo")

# Silenciadores Alto Flujo: slugs legacy y canónico; una sola entrada en menú y mismos productos.
SILENCIADORES_ALTO_FLUJO_SLUGS = ("silenciadores-alto-flujo", "silenciadores-de-alto-flujo", "silenciadores")

# Categorías flexibles: ordenar productos por medida (diámetro x largo, del más chico al más grande)
FLEXIBLES_CAT_SLUGS = ("flexibles", "flexibles-normales", "flexibles-con-extension")

# Slugs de categorías de catalíticos (para filtros técnicos en sidebar)
CATALITICOS_FILTER_SLUGS = (
    "cataliticos",
    "cataliticos-twc",
    "cataliticos-twc-euro3",
    "cataliticos-twc-euro4",
    "cataliticos-twc-euro5",
    "cataliticos-twc-diesel",
    "cataliticos-clf",
    "cataliticos-ensamble-directo",
)


def _apply_cataliticos_filters(products_qs, get_params):
    """Aplica filtros técnicos para catalíticos: euro_norm, combustible, diametro, largo, sensor, marca, modelo, cilindrada."""
    # enorm: múltiple por getlist o por query string comma-separated
    enorm_list = get_params.getlist("enorm") if hasattr(get_params, "getlist") else []
    enorm_str = (get_params.get("enorm") or "").strip()
    if enorm_str:
        enorm_list = [n.strip().upper() for n in enorm_str.split(",") if n.strip()]
    if enorm_list:
        products_qs = products_qs.filter(euro_norm__in=enorm_list)

    combustible = (get_params.get("combustible") or "").strip().upper()
    if combustible in ("BENCINA", "DIESEL"):
        products_qs = products_qs.filter(combustible=combustible)

    diametro = get_params.get("diametro")
    if diametro not in (None, ""):
        try:
            d = float(diametro)
            products_qs = products_qs.filter(diametro_entrada=d)
        except (TypeError, ValueError):
            pass

    largo = get_params.get("largo")
    if largo not in (None, ""):
        try:
            L = int(largo)
            products_qs = products_qs.filter(largo_mm=L)
        except (TypeError, ValueError):
            pass

    sensor = get_params.get("sensor")
    if sensor == "1":
        products_qs = products_qs.filter(tiene_sensor=True)
    elif sensor == "0":
        products_qs = products_qs.filter(tiene_sensor=False)

    # Filtros por compatibilidad: marca, modelo y cilindrada
    brand_id = (get_params.get("brand_id") or "").strip()
    if brand_id.isdigit():
        products_qs = products_qs.filter(
            compatibilities__brand_id=int(brand_id),
            compatibilities__is_active=True,
        )

    model_id = (get_params.get("model_id") or "").strip()
    if model_id.isdigit():
        products_qs = products_qs.filter(
            compatibilities__model_id=int(model_id),
            compatibilities__is_active=True,
        )

    # Cilindrada: para catalíticos usar rango recomendado (recommended_cc_min/cc_max)
    displacement_cc = (get_params.get("displacement_cc") or "").strip()
    if displacement_cc.isdigit():
        cc = int(displacement_cc)
        # Producto aplica si no tiene rango O si cc está dentro del rango
        products_qs = products_qs.filter(
            Q(recommended_cc_min__isnull=True) | Q(recommended_cc_min__lte=cc),
            Q(recommended_cc_max__isnull=True) | Q(recommended_cc_max__gte=cc),
        )

    return products_qs.distinct()


def _apply_category_filter(products_qs, cat_slug):
    """Aplica filtro por categoría (raíz o subcategoría). Incluye todos los descendientes.
    Para Ensamble Directo CLF, cat=cataliticos-clf o cataliticos-ensamble-directo muestra productos de ambas.
    Para Silenciadores Alto Flujo, cat=silenciadores o silenciadores-alto-flujo muestra productos de ambas."""
    if not cat_slug:
        return products_qs
    if cat_slug in CLF_ENSAMBLE_SLUGS:
        ids = list(
            Category.objects.filter(slug__in=CLF_ENSAMBLE_SLUGS, is_active=True).values_list("id", flat=True)
        )
        if ids:
            return products_qs.filter(category_id__in=ids)
    if cat_slug in SILENCIADORES_ALTO_FLUJO_SLUGS:
        ids = list(
            Category.objects.filter(slug__in=SILENCIADORES_ALTO_FLUJO_SLUGS, is_active=True).values_list("id", flat=True)
        )
        if ids:
            return products_qs.filter(category_id__in=ids)
    try:
        current_category = Category.objects.get(slug=cat_slug, is_active=True)
        category_ids = _get_descendant_category_ids(current_category.id)
        return products_qs.filter(category_id__in=category_ids)
    except Category.DoesNotExist:
        return products_qs


def _apply_user_sort(products_list, sort):
    """
    Aplica orden por nombre o precio según el parámetro sort.
    sort: "name" | "price" | "price_desc" | "" (vacío = mantener orden actual)
    """
    if not sort or not products_list:
        return products_list
    sort = (sort or "").strip().lower()
    if sort == "name":
        return sorted(products_list, key=lambda p: (p.name or "").lower())
    if sort == "price":
        return sorted(products_list, key=lambda p: (p.price or 0))
    if sort == "price_desc":
        return sorted(products_list, key=lambda p: (p.price or 0), reverse=True)
    return products_list


def order_products_for_display(products_list, cat_slug, sort=""):
    """
    Ordena la lista de productos igual que en el catálogo público:
    - Flexibles: por medida (diámetro x largo)
    - Euro 5: TWCAT052-16 primero
    - Si sort: por nombre o precio según el usuario
    Usado por catalog.product_list y ops.catalog_admin_list para mantener orden idéntico.
    """
    if not products_list:
        return products_list
    if cat_slug in FLEXIBLES_CAT_SLUGS:
        from apps.catalog.flexibles_nomenclature import parse_flexible_measure_from_sku

        def _flex_sort_key(p):
            parsed = parse_flexible_measure_from_sku(p.sku) if p.sku else None
            return parsed if parsed else (999.0, 999.0)

        products_list = sorted(products_list, key=_flex_sort_key)
    if cat_slug == "cataliticos-twc-euro5":
        _euro5_first_sku = "TWCAT052-16"

        def _euro5_sort_key(p):
            if p.sku and p.sku.upper() == _euro5_first_sku.upper():
                return (0, p.name or "")
            return (1, p.name or "")

        products_list = sorted(products_list, key=_euro5_sort_key)
    return _apply_user_sort(products_list, sort)


def _smart_search_queryset(products_qs: QuerySet[Product], q: str):
    """
    Búsqueda inteligente: divide en términos, busca en nombre, SKU y categoría.
    Cada término debe coincidir en al menos uno de esos campos (OR por término, AND entre términos).
    Orden: coincidencia exacta en SKU primero, luego por nombre.
    """
    if not q or not q.strip():
        return products_qs, False
    q = q.strip()
    terms = [t.strip() for t in q.split() if t.strip()]
    if not terms:
        return products_qs, False
    for term in terms:
        products_qs = products_qs.filter(
            Q(name__icontains=term)
            | Q(sku__icontains=term)
            | Q(category__name__icontains=term)
        )

    # Enriquecer con heurísticas de motor (cc / fuel / año) con degradación suave:
    is_relaxed = False
    parsed_engine = parse_engine_query(q)
    if parsed_engine.cc or parsed_engine.fuel or parsed_engine.year:
        base_qs = products_qs
        filtered = apply_engine_filter(
            base_qs,
            cc=parsed_engine.cc,
            fuel=parsed_engine.fuel,
            year=parsed_engine.year,
        )
        # Evaluar hasta 6 resultados para no hacer count() completo.
        strict_sample = list(filtered[:6])
        # Si el filtro fue demasiado agresivo, relajar Euro (año) manteniendo cc+fuel.
        if len(strict_sample) < 5 and parsed_engine.year:
            filtered_relaxed = apply_engine_filter(
                base_qs,
                cc=parsed_engine.cc,
                fuel=parsed_engine.fuel,
                year=None,
            )
            relaxed_sample = list(filtered_relaxed[:6])
            # Solo usar relajado si realmente mejora volumen.
            if len(relaxed_sample) >= len(strict_sample):
                products_qs = filtered_relaxed
                is_relaxed = True
            else:
                products_qs = filtered
        else:
            products_qs = filtered
    # Respetar orden por categoría (Resonadores, Silenciadores Alto Flujo) si está anotado
    if "_category_order" in products_qs.query.annotations:
        return products_qs.order_by("_category_order", "category__slug", "name"), is_relaxed
    return products_qs.order_by("category__name", "name"), is_relaxed


@require_GET
def product_search_api(request):
    """API JSON para búsqueda en tiempo real. Parámetros: q, cat, enorm, combustible, diametro, largo, sensor, sort."""
    q = (request.GET.get("q") or "").strip()
    cat_slug = (request.GET.get("cat") or "").strip()
    sort_param = (request.GET.get("sort") or "").strip().lower()
    if sort_param not in ("name", "price", "price_desc"):
        sort_param = ""

    # Mismo orden que product_list: Resonadores, Silenciadores Alto Flujo, resto
    _cat_order = Case(
        When(category__slug="resonadores", then=0),
        When(category__slug="silenciadores-alto-flujo", then=1),
        When(category__slug="silenciadores", then=2),
        default=99,
        output_field=IntegerField(),
    )
    products_qs = (
        Product.objects.filter(deleted_at__isnull=True)
        .select_related("category", "category__parent")
        .annotate(_category_order=_cat_order)
        .order_by("_category_order", "category__slug", "name")
    )
    products_qs = _apply_category_filter(products_qs, cat_slug)
    if cat_slug in CATALITICOS_FILTER_SLUGS:
        products_qs = _apply_cataliticos_filters(products_qs, request.GET)
    products_qs, is_relaxed = _smart_search_queryset(products_qs, q)
    products_list = list(products_qs[:60])  # límite razonable para respuesta rápida

    # Log de búsqueda (vista principal de catálogo / buscador global).
    parsed_engine = parse_engine_query(q)
    try:
        SearchLog.objects.create(
            query=q,
            cc=parsed_engine.cc,
            fuel=parsed_engine.fuel,
            year=parsed_engine.year,
            results_count=len(products_list),
            is_relaxed=is_relaxed,
        )
    except Exception:
        # Nunca afectar UX por un error de logging.
        pass
    products_list = order_products_for_display(products_list, cat_slug, sort_param)

    results = []
    placeholder_url = (settings.STATIC_URL or "/static/").rstrip("/") + "/img/placeholder-product.svg"
    for p in products_list:
        img = p.images.filter(position=1).first() or p.images.first()
        image_url = placeholder_url
        if img and img.image:
            image_url = img.image.url if img.image.url.startswith("http") or img.image.url.startswith("/") else (settings.MEDIA_URL.rstrip("/") + "/" + img.image.url)
        results.append({
            "sku": p.sku,
            "name": p.name,
            "slug": p.slug,
            "price_display": format_pesos_cl(p.price),
            "url": f"/productos/{p.slug}/",
            "image_url": image_url,
            "category_name": p.category.name,
            "category_slug": p.category.slug,
            "category_parent": p.category.parent.name if p.category.parent_id else "",
            "euro_norm": p.euro_norm or "",
            "euro_norm_display": p.get_euro_norm_display() if p.euro_norm else "",
            "euro_norm_slug": (p.euro_norm or "").lower(),
            "install_type": p.install_type or "",
            "combustible": p.combustible or "",
            "diametro_entrada": str(p.diametro_entrada) if p.diametro_entrada is not None else "",
            "largo_mm": p.largo_mm,
            "tiene_sensor": p.tiene_sensor,
            "is_active": p.is_active,
        })
    return JsonResponse({"products": results, "count": len(results)})


def product_list(request):
    """Listado de productos con filtro por categoría y subcategoría."""
    q = request.GET.get("q", "").strip()
    cat_slug = request.GET.get("cat", "").strip()
    # Unificar flexibles: una sola categoría "Flexibles Reforzados" (canonical slug = flexibles)
    if cat_slug == "flexibles-reforzados":
        params = request.GET.copy()
        params["cat"] = "flexibles"
        return redirect(reverse("catalog:product_list") + "?" + params.urlencode())
    anno = request.GET.get("anno", "").strip()
    wizard_fuel = request.GET.get("fuel", "").strip()
    wizard_tipo = request.GET.get("tipo", "").strip()
    wizard_anno = request.GET.get("anno", "").strip() or anno

    # Asistente de selección (solo año): redirigir a subcategoría Euro solo si no viene del wizard completo
    # Evitar redirigir cuando ya estamos en la URL destino (evita ERR_TOO_MANY_REDIRECTS)
    if anno and not q and not (wizard_fuel and wizard_tipo):
        euro_slug = _year_to_euro_cat_slug(anno)
        if euro_slug and cat_slug != euro_slug:
            url = reverse("catalog:product_list") + f"?cat={euro_slug}&anno={anno}"
            return redirect(url)

    # Categorías raíz con sus hijas (para el filtro del sidebar)
    root_categories = (
        Category.objects.filter(is_active=True, parent__isnull=True)
        .prefetch_related("children")
        .order_by("name")
    )
    root_categories = list(root_categories)
    # Si no hay raíces, mostrar como “raíces” las categorías activas que tengan productos (p. ej. tras carga Excel)
    if not root_categories:
        root_categories = list(
            Category.objects.filter(is_active=True)
            .annotate(num_products=Count("products", filter=Q(products__deleted_at__isnull=True)))
            .filter(num_products__gt=0)
            .order_by("name")
        )
        for r in root_categories:
            r.children_list = []
    else:
        # Orden: subcategorías de Cataliticos (TWG, CLF, Ensamble Directo); Euro 3/4/5/Diesel bajo TWG
        CATALITICOS_CHILD_ORDER = ("cataliticos-twc", "cataliticos-clf", "cataliticos-ensamble-directo")
        EURO_TWC_SLUG_ORDER = ("cataliticos-twc-euro3", "cataliticos-twc-euro4", "cataliticos-twc-euro5", "cataliticos-twc-diesel")

        for r in root_categories:
            children = [c for c in r.children.all() if c.is_active]
            if r.slug == "cataliticos" and children:
                children.sort(key=lambda c: (CATALITICOS_CHILD_ORDER.index(c.slug) if c.slug in CATALITICOS_CHILD_ORDER else 99, c.slug))
            elif r.slug == "cataliticos-twc" and children:
                children.sort(key=lambda c: (EURO_TWC_SLUG_ORDER.index(c.slug) if c.slug in EURO_TWC_SLUG_ORDER else 99, c.slug))
            r.children_list = children
            # Tercer nivel: subcategorías de Cataliticos TWG (Euro 3, Euro 4, Euro 5, Diesel)
            for sub in r.children_list:
                sub_children = [c for c in sub.children.all() if c.is_active]
                if sub.slug == "cataliticos-twc" and sub_children:
                    sub_children.sort(key=lambda c: (EURO_TWC_SLUG_ORDER.index(c.slug) if c.slug in EURO_TWC_SLUG_ORDER else 99, c.slug))
                sub.children_list = sub_children
        # Incluir categorías con productos que no estén en el árbol (p. ej. Silenciadores)
        ids_in_tree = {r.id for r in root_categories}
        for r in root_categories:
            ids_in_tree.update(c.id for c in r.children_list)
            for sub in r.children_list:
                ids_in_tree.update(c.id for c in sub.children_list)
        missing_ids = set(
            Category.objects.filter(is_active=True)
            .annotate(num_products=Count("products", filter=Q(products__deleted_at__isnull=True)))
            .filter(num_products__gt=0)
            .values_list("id", flat=True)
        ) - ids_in_tree
        if missing_ids:
            extra = list(Category.objects.filter(id__in=missing_ids).order_by("name"))
            for e in extra:
                e.children_list = []
            root_categories = root_categories + extra
            root_categories.sort(key=lambda x: x.name)
        # Excluir categorías antiguas reemplazadas por silenciador-linea-dw, silenciador-alto-flujo-lt, resonador-deportivo-alto-flujo-ltm
        exclude_old_slugs = (
            "flexibles-reforzados",
            "por-clasificar",
            "silenciadores",
            "silenciadores-alto-flujo",
            "silenciadores-de-alto-flujo",
            "resonadores",
        )
        root_categories = [r for r in root_categories if r.slug not in exclude_old_slugs]


    # Orden: Resonadores primero, luego Silenciadores Alto Flujo, luego resto; después por nombre
    CAT_ORDER = [
        ("resonadores", 0),
        ("silenciadores-alto-flujo", 1),
        ("silenciadores-de-alto-flujo", 2),
        ("silenciadores", 3),  # slug legacy por si existe
    ]
    category_order_cases = [
        When(category__slug=slug, then=order) for slug, order in CAT_ORDER
    ]
    products_qs = (
        Product.objects.filter(deleted_at__isnull=True)
        .select_related("category", "category__parent")
        .prefetch_related("images")
        .annotate(
            _category_order=Case(
                *category_order_cases,
                default=99,
                output_field=IntegerField(),
            )
        )
        .order_by("_category_order", "category__slug", "name")
    )

    products_qs, is_relaxed = _smart_search_queryset(products_qs, q)

    current_category = None
    expanded_root_ids = set()

    # Filtro desde Asistente de Selección (wizard): combustible + año + tipo
    if wizard_fuel and wizard_tipo:
        wizard_slugs = _wizard_resolve_category_slugs(wizard_fuel, wizard_anno, wizard_tipo)
        if wizard_slugs:
            products_qs = products_qs.filter(category__slug__in=wizard_slugs)
            try:
                current_category = Category.objects.select_related("parent", "parent__parent").get(
                    slug=wizard_slugs[0], is_active=True
                )
                cat_slug = wizard_slugs[0]
                cat_root = Category.objects.filter(slug="cataliticos", parent__isnull=True).values_list("id", flat=True).first()
                if cat_root:
                    expanded_root_ids.add(cat_root)
            except Category.DoesNotExist:
                pass
    elif cat_slug:
        try:
            # Unificar Ensamble Directo CLF: si piden cataliticos-clf, usar cataliticos-ensamble-directo para current_category
            slug_for_lookup = cat_slug
            if cat_slug in CLF_ENSAMBLE_SLUGS:
                slug_for_lookup = "cataliticos-ensamble-directo"
                category_ids = list(
                    Category.objects.filter(slug__in=CLF_ENSAMBLE_SLUGS, is_active=True).values_list("id", flat=True)
                )
                products_qs = products_qs.filter(category_id__in=category_ids)
                current_category = Category.objects.select_related("parent", "parent__parent").get(
                    slug=slug_for_lookup, is_active=True
                )
            elif cat_slug in SILENCIADORES_ALTO_FLUJO_SLUGS:
                category_ids = list(
                    Category.objects.filter(slug__in=SILENCIADORES_ALTO_FLUJO_SLUGS, is_active=True).values_list("id", flat=True)
                )
                products_qs = products_qs.filter(category_id__in=category_ids)
                # Canonical para breadcrumb: silenciadores-alto-flujo si existe, si no silenciadores
                current_category = (
                    Category.objects.select_related("parent", "parent__parent").filter(slug="silenciadores-alto-flujo", is_active=True).first()
                    or Category.objects.select_related("parent", "parent__parent").filter(slug="silenciadores", is_active=True).first()
                )
            else:
                current_category = Category.objects.select_related("parent", "parent__parent").get(
                    slug=slug_for_lookup, is_active=True
                )
                category_ids = _get_descendant_category_ids(current_category.id)
                # Unificar flexibles: incluir también productos de la raíz "flexibles-reforzados" si existe
                if slug_for_lookup == "flexibles":
                    cat_ref = Category.objects.filter(slug="flexibles-reforzados", is_active=True).first()
                    if cat_ref:
                        category_ids = list(set(category_ids) | set(_get_descendant_category_ids(cat_ref.id)))
                products_qs = products_qs.filter(category_id__in=category_ids)
            # Marcar qué raíces deben mostrarse expandidas (para Cataliticos > TWG > Euro 3/4/5/Diesel)
            if current_category:
                if current_category.parent_id is None:
                    expanded_root_ids.add(current_category.id)
                elif current_category.parent.parent_id is None:
                    expanded_root_ids.add(current_category.parent_id)
                else:
                    expanded_root_ids.add(current_category.parent.parent_id)
        except Category.DoesNotExist:
            pass

    # Cuando se filtra por "cataliticos" o "flexibles", mostrar vista de elección (cards por subcategoría)
    show_cataliticos_choice = False
    euro_categories_with_previews = []
    cataliticos_nivel1 = []
    show_flexibles_choice = False
    flexibles_categories_with_previews = []
    if cat_slug == "cataliticos" and not q:
        # Nivel 1: Universales (TWG) | Ensamble Directo (CLF)
        # Nivel 2 (TWG): Euro 3, Euro 4, Euro 5 — Nivel 3 (TWG): Bencineros (Euro 3/4/5) + Diesel
        subcat_slugs_twg = (
            "cataliticos-twc-euro3",
            "cataliticos-twc-euro4",
            "cataliticos-twc-euro5",
            "cataliticos-twc-diesel",
        )
        subcat_slugs_clf = ("cataliticos-clf", "cataliticos-ensamble-directo")
        subcat_slugs = subcat_slugs_twg + subcat_slugs_clf
        subcategories = list(
            Category.objects.filter(slug__in=subcat_slugs, is_active=True)
        )
        order = {s: i for i, s in enumerate(subcat_slugs)}
        subcategories.sort(key=lambda c: order.get(c.slug, 99))

        def _preview_for_cat(category):
            products = list(
                Product.objects.filter(category=category, is_active=True)
                .prefetch_related("images")[:14]
            )
            urls = []
            for p in products:
                img = p.images.order_by("position").first()
                if img and img.image:
                    urls.append(img.image.url)
            return urls

        def _preview_for_clf():
            """Imágenes de productos de ambas categorías Ensamble Directo CLF (máx 14)."""
            products = list(
                Product.objects.filter(category__slug__in=CLF_ENSAMBLE_SLUGS, is_active=True)
                .prefetch_related("images")[:14]
            )
            urls = []
            for p in products:
                img = p.images.order_by("position").first()
                if img and img.image:
                    urls.append(img.image.url)
            return urls

        # Labels para Nivel 2/3 (Euro y combustible)
        euro_display = {
            "cataliticos-twc-euro3": "Euro 3",
            "cataliticos-twc-euro4": "Euro 4",
            "cataliticos-twc-euro5": "Euro 5",
            "cataliticos-twc-diesel": "Diesel (DOC/DPF)",
        }
        twg_items = []
        for slug in subcat_slugs_twg:
            cat = next((c for c in subcategories if c.slug == slug), None)
            if cat:
                twg_items.append({
                    "category": cat,
                    "preview_urls": _preview_for_cat(cat),
                    "display_label": euro_display.get(slug, cat.name),
                    "badge_euro": euro_display.get(slug, ""),
                })
        # Una sola tarjeta "Ensamble Directo CLF" (enlace a cataliticos-ensamble-directo; productos de ambas)
        clf_items = []
        cat_ensamble = next((c for c in subcategories if c.slug == "cataliticos-ensamble-directo"), None)
        if cat_ensamble:
            clf_items.append({
                "category": cat_ensamble,
                "preview_urls": _preview_for_clf(),
                "display_label": "Ensamble Directo CLF",
                "badge_euro": "",
            })
        cataliticos_nivel1 = [
            {
                "label": "Universales (Marca TWG)",
                "subtitle": "Para instalación con soldadura",
                "items": twg_items,
            },
            {
                "label": "Ensamble Directo CLF",
                "subtitle": "Plug & Play por modelo",
                "items": clf_items,
            },
        ]
        # Mantener lista plana para compatibilidad con template que itera euro_categories_with_previews
        for item in twg_items + clf_items:
            euro_categories_with_previews.append({
                "category": item["category"],
                "preview_urls": item["preview_urls"],
                "display_label": item.get("display_label"),
                "badge_euro": item.get("badge_euro", ""),
            })
        show_cataliticos_choice = True

    # Cuando se filtra por "flexibles", mostrar vista de elección: Flexibles Reforzados | Flexibles Reforzados con extensión
    show_flexibles_choice = False
    flexibles_categories_with_previews = []
    if cat_slug == "flexibles" and not q:
        subcat_slugs = ("flexibles-normales", "flexibles-con-extension")
        subcategories = list(
            Category.objects.filter(slug__in=subcat_slugs, is_active=True)
        )
        # Labels: todos son reforzados
        display_labels = {"flexibles-normales": "Flexibles Reforzados", "flexibles-con-extension": "Flexibles Reforzados con extensión"}
        order = {s: i for i, s in enumerate(subcat_slugs)}
        subcategories.sort(key=lambda c: order.get(c.slug, 99))
        for cat in subcategories:
            products = list(
                Product.objects.filter(category=cat, is_active=True)
                .prefetch_related("images")[:14]
            )
            urls = []
            for p in products:
                img = p.images.order_by("position").first()
                if img and img.image:
                    urls.append(img.image.url)
            label = display_labels.get(cat.slug, cat.name)
            count = Product.objects.filter(category=cat, deleted_at__isnull=True).count()
            flexibles_categories_with_previews.append({
                "category": cat,
                "preview_urls": urls,
                "display_label": label,
                "product_count": count,
            })
        show_flexibles_choice = True

    # Vista de catalíticos en subcategoría: grid mosaico con imagen protagonista y badges Euro/tipo
    cataliticos_subcat_slugs = (
        "cataliticos-twc", "cataliticos-twc-euro3", "cataliticos-twc-euro4",
        "cataliticos-twc-euro5", "cataliticos-twc-diesel",
        "cataliticos-clf", "cataliticos-ensamble-directo",
    )
    if cat_slug in cataliticos_subcat_slugs or (wizard_fuel and wizard_tipo):
        products_qs = products_qs.prefetch_related("compatibilities__model__brand")

    # Filtros técnicos para catalíticos (norma, combustible, diámetro, largo, sensor)
    cataliticos_filter_options = {}
    if cat_slug in CATALITICOS_FILTER_SLUGS and not (show_cataliticos_choice or show_flexibles_choice):
        base_cataliticos = products_qs
        euro_norms_qs = list(
            base_cataliticos.filter(euro_norm__isnull=False)
            .values_list("euro_norm", flat=True)
            .distinct()
            .order_by("euro_norm")
        )
        euro_norm_labels = dict(Product._meta.get_field("euro_norm").choices)
        cataliticos_filter_options = {
            "euro_norms": euro_norms_qs,
            "euro_norm_options": [(n, euro_norm_labels.get(n, n)) for n in euro_norms_qs],
            "combustibles": list(
                base_cataliticos.filter(combustible__isnull=False)
                .values_list("combustible", flat=True)
                .distinct()
                .order_by("combustible")
            ),
            "diametros": list(
                base_cataliticos.filter(diametro_entrada__isnull=False)
                .values_list("diametro_entrada", flat=True)
                .distinct()
                .order_by("diametro_entrada")
            ),
            "largos_mm": list(
                base_cataliticos.filter(largo_mm__isnull=False)
                .values_list("largo_mm", flat=True)
                .distinct()
                .order_by("largo_mm")
            ),
            "tiene_sensor_choices": [True, False],
        }
        products_qs = _apply_cataliticos_filters(products_qs, request.GET)

    # Cuando mostramos pantalla de elección (catalíticos o flexibles), no mostrar grid de productos
    products_to_show = [] if (show_cataliticos_choice or show_flexibles_choice) else list(products_qs)
    sort_param = (request.GET.get("sort") or "").strip().lower()
    if sort_param not in ("name", "price", "price_desc"):
        sort_param = ""
    products_to_show = order_products_for_display(products_to_show, cat_slug, sort_param)
    is_cataliticos_subcat = cat_slug in cataliticos_subcat_slugs and bool(products_to_show or q)
    anno_sugerido = request.GET.get("anno", "").strip()

    # Etiqueta Euro para resultados del wizard (solo TWG bencina)
    wizard_euro_display = ""
    if wizard_fuel and wizard_tipo and wizard_anno and wizard_tipo == "twg" and wizard_fuel != "diesel":
        euro_val = _wizard_year_to_euro(wizard_anno)
        wizard_euro_display = {"EURO3": "Euro 3", "EURO4": "Euro 4", "EURO5": "Euro 5"}.get(euro_val or "", "")

    # Parámetros de filtros técnicos (para mantener en URL y sidebar)
    filter_enorm_list = request.GET.getlist("enorm")
    filter_enorm = ",".join(filter_enorm_list)  # para API
    filter_combustible = (request.GET.get("combustible") or "").strip()
    filter_diametro = (request.GET.get("diametro") or "").strip()
    filter_largo = (request.GET.get("largo") or "").strip()
    filter_sensor = (request.GET.get("sensor") or "").strip()

    return render(
        request,
        "catalog/product_list.html",
        {
            "products": products_to_show,
            "q": q,
            "root_categories": root_categories,
            "current_category": current_category,
            "cat_slug": cat_slug,
            "expanded_root_ids": expanded_root_ids,
            "show_cataliticos_choice": show_cataliticos_choice,
            "euro_categories_with_previews": euro_categories_with_previews,
            "cataliticos_nivel1": cataliticos_nivel1 if show_cataliticos_choice else [],
            "show_flexibles_choice": show_flexibles_choice,
            "flexibles_categories_with_previews": flexibles_categories_with_previews,
            "is_cataliticos_subcat": is_cataliticos_subcat,
            "anno_sugerido": anno_sugerido,
            "wizard_fuel": wizard_fuel,
            "wizard_tipo": wizard_tipo,
            "wizard_anno": wizard_anno,
            "wizard_euro_display": wizard_euro_display,
            "is_relaxed": is_relaxed,
            "cataliticos_filter_options": cataliticos_filter_options,
            "filter_enorm_list": filter_enorm_list,
            "filter_enorm": filter_enorm,
            "filter_combustible": filter_combustible,
            "filter_diametro": filter_diametro,
            "filter_largo": filter_largo,
            "filter_sensor": filter_sensor,
            "sort_param": sort_param,
        },
    )


def asistente_cataliticos(request):
    """Asistente de selección inteligente: 3 pasos (Combustible → Año → Tipo)."""
    return render(request, "catalog/asistente_cataliticos.html")


def normativas(request):
    """Landing educativa: historia y diferencias de las normas Euro para catalíticos."""
    return render(request, "catalog/normativas.html")


def cataliticos_twg_opciones(request):
    """Página de opciones/fichas para Convertidores Catalíticos TWG: Euro 3, Euro 4, Euro 5, Diesel."""
    EURO_TWC_SLUG_ORDER = (
        "cataliticos-twc-euro3",
        "cataliticos-twc-euro4",
        "cataliticos-twc-euro5",
        "cataliticos-twc-diesel",
    )
    euro_display = {
        "cataliticos-twc-euro3": "Euro 3",
        "cataliticos-twc-euro4": "Euro 4",
        "cataliticos-twc-euro5": "Euro 5",
        "cataliticos-twc-diesel": "Diesel",
    }
    categories = list(
        Category.objects.filter(slug__in=EURO_TWC_SLUG_ORDER, is_active=True)
    )
    order = {s: i for i, s in enumerate(EURO_TWC_SLUG_ORDER)}
    categories.sort(key=lambda c: order.get(c.slug, 99))

    def _preview_for_cat(category):
        products = list(
            Product.objects.filter(category=category, is_active=True)
            .prefetch_related("images")[:10]
        )
        urls = []
        for p in products:
            img = p.images.order_by("position").first()
            if img and img.image:
                urls.append(img.image.url)
        return urls

    euro_options = []
    for cat in categories:
        euro_options.append({
            "slug": cat.slug,
            "label": euro_display.get(cat.slug, cat.name),
            "url": reverse("catalog:product_list") + "?cat=" + cat.slug,
            "preview_urls": _preview_for_cat(cat),
        })

    return render(
        request,
        "catalog/cataliticos_twg_opciones.html",
        {"euro_options": euro_options},
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.filter(deleted_at__isnull=True)
        .select_related("category")
        .prefetch_related(
            Prefetch(
                "images",
                queryset=ProductImage.objects.order_by("-is_primary", "position"),
            ),
            Prefetch(
                "compatibilities",
                queryset=ProductCompatibility.objects.filter(is_active=True)
                .select_related("brand", "model", "engine")
                .order_by("brand__name", "model__name", "year_from", "year_to"),
            ),
        ),
        slug=slug,
    )
    # Conteo de vistas por sesión (una por producto por sesión; evita bots/recargas)
    session_key = f"viewed_product_{product.id}"
    if not request.session.get(session_key):
        stat, _ = ProductViewStat.objects.get_or_create(product=product)
        stat.views += 1
        stat.save(update_fields=["views", "last_viewed"])
        request.session[session_key] = True

    related_products = (
        Product.objects.filter(
            category=product.category,
            is_active=True,
            deleted_at__isnull=True,
        )
        .exclude(pk=product.pk)
        .select_related("category")
        .prefetch_related("images")
        .order_by("name")[:8]
    )

    # Compatibilidades: lista plana + agrupada por marca para el template
    compat_qs = list(product.compatibilities.all())
    compat_by_brand = OrderedDict()
    for c in compat_qs:
        brand_name = c.brand.name if c.brand else "Sin marca"
        compat_by_brand.setdefault(brand_name, []).append(c)

    # SEO meta: lista única (evitar "Chevrolet Cruze, Chevrolet Cruze, ...")
    compat_seen = set()
    seo_vehicle_compatibility_list = []
    for c in compat_qs:
        if c.brand:
            key = f"{c.brand.name} {c.model.name if c.model else 'todos los modelos'}"
            if key not in compat_seen:
                compat_seen.add(key)
                seo_vehicle_compatibility_list.append(key)
    seo_vehicle_compatibility = ", ".join(seo_vehicle_compatibility_list)

    # Schema.org: vehículos únicos para isAccessoryOrSparePartFor
    schema_vehicles_seen = set()
    schema_vehicles = []
    for c in compat_qs:
        if c.brand:
            key = (c.brand.name, c.model.name if c.model else "Todos los modelos")
            if key not in schema_vehicles_seen:
                schema_vehicles_seen.add(key)
                schema_vehicles.append({"brand": c.brand.name, "model": key[1]})

    # Tabla limitada a 100 filas; si hay más, mostramos aviso + enlace a lista completa
    compat_table_limit = 100
    compat = compat_qs[:compat_table_limit]
    compat_count_total = len(compat_qs)

    # Resumen para buybox (primeras 3 marcas, 4 aplicaciones por marca) sin depender de slice en template
    compat_preview = []
    for i, (bname, blist) in enumerate(compat_by_brand.items()):
        if i >= 3:
            break
        compat_preview.append((bname, blist[:4], len(blist)))

    from apps.catalog.flexibles_nomenclature import get_flexible_dimensions_display
    flexible_dims = get_flexible_dimensions_display(product.sku) or ""

    # Mejora 2: enlace "Ver todos los 2x6" cuando el producto tiene diámetro y largo
    busqueda_medidas_url = None
    busqueda_medidas_label = None
    if product.largo_mm and (product.diametro_entrada is not None or product.diametro_salida is not None):
        d = product.diametro_entrada if product.diametro_entrada is not None else product.diametro_salida
        d_label = str(int(d)) if d == int(d) else str(d)
        largo_pulg = round(product.largo_mm / 25.4, 1)
        label_largo = str(int(largo_pulg)) if largo_pulg == int(largo_pulg) else str(largo_pulg)
        busqueda_medidas_url = reverse("catalog:buscar_escape") + f"?diametro={d_label}&largo={product.largo_mm}"
        busqueda_medidas_label = f"Ver todos los {d_label}x{label_largo}"

    # Ficha técnica industrial para catalíticos (TWG/CLF)
    cat_slug = (product.category.slug if product.category_id else "") or ""
    is_catalitico = (
        product.euro_norm is not None
        or cat_slug.startswith("cataliticos-twc")
        or cat_slug in ("cataliticos-clf", "cataliticos-ensamble-directo")
    )

    # Ensamble directo (CLF): aplicaciones para buybox y bloque destacado (todos los SKUs de la categoría)
    _direct_fit_slugs = ("cataliticos-clf", "cataliticos-ensamble-directo")
    is_direct_fit_clf = cat_slug in _direct_fit_slugs
    direct_fit_application_rows = []
    if is_direct_fit_clf and compat_qs:
        for c in compat_qs[:60]:
            direct_fit_application_rows.append(
                {
                    "brand": c.brand.name if c.brand_id else "—",
                    "model": c.model.name if c.model_id else "Todos los modelos",
                    "years": (
                        "consultar aplicación"
                        if c.year_from == 1900 and c.year_to == 2100
                        else f"{c.year_from}–{c.year_to}"
                    ),
                }
            )

    # Reseñas aprobadas
    from apps.reviews.models import Review
    from apps.reviews.services import user_can_review
    approved_reviews = list(Review.objects.filter(product=product, is_approved=True).select_related("user")[:20])
    can_review = user_can_review(request.user, product)
    user_review = None
    if request.user.is_authenticated:
        user_review = Review.objects.filter(product=product, user=request.user).first()
    # Stats para Schema aggregateRating
    review_stats = {"count": len(approved_reviews)}
    if approved_reviews:
        review_stats["avg"] = round(sum(r.rating for r in approved_reviews) / len(approved_reviews), 1)
    else:
        review_stats["avg"] = 0

    return render(
        request,
        "catalog/product_detail.html",
        {
            "product": product,
            "compat": compat,
            "compatibilities": compat_qs,
            "compatibilities_by_brand": list(compat_by_brand.items()),
            "seo_vehicle_compatibility": seo_vehicle_compatibility,
            "schema_vehicles": schema_vehicles,
            "compat_count_total": compat_count_total,
            "compat_table_limit": compat_table_limit,
            "compat_preview": compat_preview,
            "related_products": related_products,
            "flexible_dims": flexible_dims,
            "busqueda_medidas_url": busqueda_medidas_url,
            "busqueda_medidas_label": busqueda_medidas_label,
            "is_catalitico": is_catalitico,
            "is_direct_fit_clf": is_direct_fit_clf,
            "direct_fit_application_rows": direct_fit_application_rows,
            "approved_reviews": approved_reviews,
            "can_review": can_review,
            "user_review": user_review,
            "review_stats": review_stats,
        },
    )


def lista_precios(request):
    """Listado de precios para imprimir o llevar. Productos activos ordenados por categoría y SKU."""
    products = (
        Product.objects.filter(is_active=True, deleted_at__isnull=True)
        .select_related("category")
        .order_by("category__name", "sku")
    )
    return render(
        request,
        "catalog/lista_precios.html",
        {
            "products": products,
        },
    )


# Opciones para buscador por medidas (diámetro en pulgadas, largo en mm)
DIAMETRO_OPCIONES = [
    ("1.5", "1.5 pulgadas"),
    ("1.75", "1.75 pulgadas"),
    ("2", "2 pulgadas"),
    ("2.25", "2.25 pulgadas"),
    ("2.5", "2.5 pulgadas"),
    ("3", "3 pulgadas"),
    ("3.5", "3.5 pulgadas"),
]
LARGO_MM_OPCIONES = [
    ("102", "4 pulgadas (102 mm)"),
    ("152", "6 pulgadas (152 mm)"),
    ("203", "8 pulgadas (203 mm)"),
    ("254", "10 pulgadas (254 mm)"),
    ("305", "12 pulgadas (305 mm)"),
]


def _parse_q_medidas(q):
    """Interpreta búsquedas tipo 2x6, 2 x 6, 2*6, 2,5x8. Retorna (diametro_str, largo_str) o (None, None)."""
    from decimal import Decimal, InvalidOperation
    if not q or ("x" not in q.lower() and "*" not in q):
        return None, None
    q = q.strip().lower().replace("*", "x")
    parts = q.split("x", 1)
    if len(parts) != 2:
        return None, None
    try:
        raw_d = parts[0].strip().replace(",", ".")
        raw_l = parts[1].strip().replace(",", ".")
        d = Decimal(raw_d)
        l_inch = float(raw_l)
        l_mm = int(round(l_inch * 25.4))
        return str(d), str(l_mm)
    except (InvalidOperation, ValueError, TypeError):
        return None, None


def buscar_escape(request):
    """Búsqueda por diámetro y/o largo. Soporta q=2x6. Muy usada por talleres."""
    from decimal import Decimal, InvalidOperation
    from django.db.models import Case, Value, When

    diametro = request.GET.get("diametro", "").strip()
    largo = request.GET.get("largo", "").strip()
    q = request.GET.get("q", "").strip()

    # Mejora 1: interpretar 2x6, 2 x 6, 2*6
    if q:
        parsed_d, parsed_l = _parse_q_medidas(q)
        if parsed_d:
            diametro = parsed_d
        if parsed_l:
            largo = parsed_l

    base = Product.objects.filter(is_active=True, deleted_at__isnull=True).select_related("category")
    products = base.order_by("category__name", "name")

    diametro_dec = None
    largo_int = None

    if diametro:
        try:
            diametro_dec = Decimal(diametro)
            products = products.filter(
                Q(diametro_entrada=diametro_dec) | Q(diametro_salida=diametro_dec)
            )
        except (InvalidOperation, ValueError):
            pass

    if largo:
        try:
            largo_int = int(largo)
            products = products.filter(largo_mm=largo_int)
        except ValueError:
            pass

    # Mejora 5: orden inteligente — exactos primero, luego compatibles (solo diámetro), luego resto
    if diametro_dec is not None or largo_int is not None:
        whens = []
        if diametro_dec is not None and largo_int is not None:
            whens.append(
                When(
                    (Q(diametro_entrada=diametro_dec) | Q(diametro_salida=diametro_dec))
                    & Q(largo_mm=largo_int),
                    then=Value(2),
                )
            )
        if diametro_dec is not None:
            whens.append(
                When(
                    Q(diametro_entrada=diametro_dec) | Q(diametro_salida=diametro_dec),
                    then=Value(1),
                )
            )
        if whens:
            products = products.annotate(
                _match_score=Case(*whens, default=Value(0), output_field=IntegerField())
            ).order_by("-_match_score", "category__name", "name")

    products = list(products[:50])

    # Mejora 3: opciones dinámicas (solo medidas que existen en productos activos)
    diametro_entrada_set = set(
        base.exclude(diametro_entrada__isnull=True)
        .values_list("diametro_entrada", flat=True)
        .distinct()
    )
    diametro_salida_set = set(
        base.exclude(diametro_salida__isnull=True)
        .values_list("diametro_salida", flat=True)
        .distinct()
    )
    def _d_str(d):
        return str(int(d)) if d == int(d) else str(d)
    all_diametros = sorted({_d_str(d) for d in (diametro_entrada_set | diametro_salida_set)})
    largo_values = sorted(
        base.exclude(largo_mm__isnull=True).values_list("largo_mm", flat=True).distinct()
    )
    diametro_opciones = [(v, f"{v} pulgadas") for v in all_diametros] if all_diametros else DIAMETRO_OPCIONES
    largo_opciones = (
        [(str(l), f"{round(l / 25.4, 1)} pulgadas ({l} mm)") for l in largo_values]
        if largo_values
        else LARGO_MM_OPCIONES
    )

    # Mejora 7: agrupar por categoría para mostrar "Flexibles 2\"", "Silenciadores 2\"", etc.
    products_by_category = OrderedDict()
    for p in products:
        name = p.category.name if p.category else "Productos"
        products_by_category.setdefault(name, []).append(p)

    return render(
        request,
        "catalog/buscar_escape.html",
        {
            "products": products,
            "products_by_category": list(products_by_category.items()),
            "diametro": diametro,
            "largo": largo,
            "q": q,
            "diametro_opciones": diametro_opciones,
            "largo_opciones": largo_opciones,
        },
    )


@require_GET
def smart_search_suggestions_api(request):
    """API de sugerencias para autocomplete del buscador global. GET q -> JSON { results: [...] }."""
    from .utils.smart_search_suggestions import get_smart_search_suggestions

    q = request.GET.get("q", "").strip()
    results = get_smart_search_suggestions(q, total_limit=8)
    return JsonResponse({"results": results})


def smart_search_redirect(request):
    """
    Buscador inteligente: interpreta GET q y redirige a buscar-escape, vehicle_search o product_list.
    """
    from django.utils.http import urlencode

    from .utils.smart_search import parse_smart_search

    q = (request.GET.get("q") or "").strip()
    parsed = parse_smart_search(q)

    if parsed["type"] == "empty":
        return redirect(reverse("catalog:product_list"))

    if parsed["type"] == "measure":
        url = reverse("catalog:buscar_escape")
        params = urlencode({"q": parsed["original_query"]})
        return redirect(f"{url}?{params}")

    if parsed["type"] == "vehicle":
        # Resolver vehículo: si tenemos marca, modelo y año, podemos intentar ir directo al flujo core,
        # que es el validador principal y SEO-friendly. Si falta información clave (p. ej. año),
        # o si en el futuro se detecta ambigüedad relevante de motor, usamos el buscador de vehículo
        # en catálogo como paso intermedio para que el usuario complete datos.
        brand_id = parsed.get("brand_id")
        model_id = parsed.get("model_id")
        year = parsed.get("year")

        if brand_id and model_id and year:
            core_url = reverse("core:vehicle_search")
            core_params = {"brand": brand_id, "model": model_id, "year": year}
            return redirect(f"{core_url}?{urlencode(core_params)}")

        # Fallback: mantener flujo actual /productos/buscador-vehiculo/ como paso intermedio
        url = reverse("catalog:vehicle_search")
        params_dict = {"q": parsed["original_query"]}
        if brand_id:
            params_dict["brand_id"] = brand_id
        if model_id:
            params_dict["model_id"] = model_id
        if year:
            params_dict["year"] = year
        return redirect(f"{url}?{urlencode(params_dict)}")

    # type == "product"
    url = reverse("catalog:product_list")
    params = urlencode({"q": parsed["original_query"]})
    return redirect(f"{url}?{params}")


def escape_seo_redirect(request, diametro_slug, largo_slug=None):
    """URLs indexables tipo /escape/2-pulgadas/ y /escape/2-pulgadas/6-pulgadas/ → redirige al buscador."""
    # Parse "2-pulgadas" -> 2, "2-5-pulgadas" -> 2.5
    def parse_pulgadas(slug):
        if not slug or not slug.endswith("-pulgadas"):
            return None
        raw = slug[:-9].rstrip("-").replace("-", ".")  # "2-5-pulgadas" -> "2.5"
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None

    d = parse_pulgadas(diametro_slug)
    if d is None:
        from django.http import HttpResponseNotFound
        return HttpResponseNotFound()
    diametro = str(int(d)) if d == int(d) else str(d)
    largo_mm = None
    if largo_slug:
        l_inch = parse_pulgadas(largo_slug)
        if l_inch is not None:
            largo_mm = str(int(round(l_inch * 25.4)))
    url = reverse("catalog:buscar_escape")
    params = ["diametro=" + diametro]
    if largo_mm:
        params.append("largo=" + largo_mm)
    return redirect(url + "?" + "&".join(params))


def review_submit(request, slug):
    """Redirige al handler de reseñas en apps.reviews."""
    from apps.reviews.views import review_submit as _submit
    return _submit(request, slug)

