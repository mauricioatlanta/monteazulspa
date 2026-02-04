from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.db.models import Q, Count
from django.views.decorators.http import require_GET
from .models import Product, Category
from .templatetags.catalog_filters import format_pesos_cl


def _apply_category_filter(products_qs, cat_slug):
    """Aplica filtro por categoría (raíz o subcategoría)."""
    if not cat_slug:
        return products_qs
    try:
        current_category = Category.objects.get(slug=cat_slug, is_active=True)
        if current_category.parent_id is None:
            child_ids = list(
                Category.objects.filter(parent=current_category, is_active=True).values_list("id", flat=True)
            )
            category_ids = [current_category.id] + child_ids
            return products_qs.filter(category_id__in=category_ids)
        return products_qs.filter(category=current_category)
    except Category.DoesNotExist:
        return products_qs


def _smart_search_queryset(products_qs, q):
    """
    Búsqueda inteligente: divide en términos, busca en nombre, SKU y categoría.
    Cada término debe coincidir en al menos uno de esos campos (OR por término, AND entre términos).
    Orden: coincidencia exacta en SKU primero, luego por nombre.
    """
    if not q or not q.strip():
        return products_qs
    q = q.strip()
    terms = [t.strip() for t in q.split() if t.strip()]
    if not terms:
        return products_qs
    for term in terms:
        products_qs = products_qs.filter(
            Q(name__icontains=term)
            | Q(sku__icontains=term)
            | Q(category__name__icontains=term)
        )
    return products_qs.order_by("category__name", "name")


@require_GET
def product_search_api(request):
    """API JSON para búsqueda en tiempo real. Parámetros: q, cat (opcional)."""
    q = (request.GET.get("q") or "").strip()
    cat_slug = (request.GET.get("cat") or "").strip()

    products_qs = (
        Product.objects.filter(is_active=True, deleted_at__isnull=True)
        .select_related("category", "category__parent")
        .order_by("category__name", "name")
    )
    products_qs = _apply_category_filter(products_qs, cat_slug)
    products_qs = _smart_search_queryset(products_qs, q)
    products_qs = products_qs[:60]  # límite razonable para respuesta rápida

    results = []
    for p in products_qs:
        img = p.images.filter(position=1).first() or p.images.first()
        image_url = ""
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
            "category_parent": p.category.parent.name if p.category.parent_id else "",
        })
    return JsonResponse({"products": results, "count": len(results)})


def product_list(request):
    """Listado de productos con filtro por categoría y subcategoría."""
    q = request.GET.get("q", "").strip()
    cat_slug = request.GET.get("cat", "").strip()

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
            .annotate(num_products=Count("products", filter=Q(products__is_active=True, products__deleted_at__isnull=True)))
            .filter(num_products__gt=0)
            .order_by("name")
        )
        for r in root_categories:
            r.children_list = []
    else:
        for r in root_categories:
            r.children_list = [c for c in r.children.all() if c.is_active]

    products_qs = (
        Product.objects.filter(is_active=True, deleted_at__isnull=True)
        .select_related("category", "category__parent")
        .prefetch_related("images")
        .order_by("category__name", "name")
    )

    products_qs = _smart_search_queryset(products_qs, q)

    current_category = None
    if cat_slug:
        try:
            current_category = Category.objects.get(slug=cat_slug, is_active=True)
            if current_category.parent_id is None:
                child_ids = list(
                    Category.objects.filter(parent=current_category, is_active=True).values_list("id", flat=True)
                )
                category_ids = [current_category.id] + child_ids
                products_qs = products_qs.filter(category_id__in=category_ids)
            else:
                products_qs = products_qs.filter(category=current_category)
        except Category.DoesNotExist:
            pass

    return render(
        request,
        "catalog/product_list.html",
        {
            "products": products_qs,
            "q": q,
            "root_categories": root_categories,
            "current_category": current_category,
            "cat_slug": cat_slug,
        },
    )


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related(
            "images", "compatibilities"
        ),
        slug=slug,
        is_active=True,
        deleted_at__isnull=True,
    )
    # "Modo validado" vendrá en el siguiente paso: se lee desde session['fitment']
    return render(request, "catalog/product_detail.html", {"product": product})

