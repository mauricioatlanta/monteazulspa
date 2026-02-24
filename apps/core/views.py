from django.conf import settings
from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.utils.http import urlencode
from django.urls import reverse
from .chile_regiones_comunas import get_regiones, get_comunas_por_region
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from django.db.models import Prefetch, Count
from apps.catalog.models import Category, Product, ProductImage, VehicleBrand, VehicleModel, VehicleEngine, ProductCompatibility


def home(request):
    """Página de bienvenida al sitio monteazulspa.cl. Incluye imágenes de productos para el hero."""
    media_url = (getattr(settings, 'MEDIA_URL') or '/media/').rstrip('/')
    # Usar .values() / values_list() para que el SQL solo toque columnas básicas; así la home
    # funciona aunque migraciones 0009/0010/0011 (sku_canonico, combustible, etc.) no estén aplicadas.
    product_ids = list(
        Product.objects.filter(
            is_publishable=True,
            is_active=True,
            deleted_at__isnull=True,
        )
        .annotate(img_count=Count('images'))
        .filter(img_count__gt=0)
        .values_list('id', flat=True)
        .distinct()[:16]
    )
    if not product_ids:
        products_data = {}
        first_image_by_product = {}
    else:
        products_data = {
            p['id']: p
            for p in Product.objects.filter(id__in=product_ids).values('id', 'name', 'sku', 'slug')
        }
        # Primera imagen por producto (misma lógica que antes: is_primary primero, luego position)
        first_image_by_product = {}
        for img in (
            ProductImage.objects.filter(product_id__in=product_ids)
            .order_by('product_id', '-is_primary', 'position')
        ):
            if img.product_id not in first_image_by_product:
                first_image_by_product[img.product_id] = img
    hero_slides = []
    featured_products = []
    for pid in product_ids:
        p = products_data.get(pid)
        if not p:
            continue
        img = first_image_by_product.get(pid)
        if not img or not img.image:
            continue
        url = img.image.url if (img.image.url.startswith('http') or img.image.url.startswith('/')) else f"{media_url}/{img.image.name}"
        item = {
            'image_url': url,
            'name': p['name'],
            'sku': p['sku'],
            'slug': p['slug'],
            'url': f'/productos/{p["slug"]}/',
        }
        hero_slides.append(item)
        if len(featured_products) < 8:
            featured_products.append(dict(item))
        if len(hero_slides) >= 12:
            break
    # Fallback si no hay imágenes de productos: banners estáticos
    if not hero_slides:
        hero_slides = [
            {'image_url': f'{media_url}banners/banner_twcat003.png', 'name': 'Catalítico TWCAT003', 'sku': 'TWCAT003', 'url': '/productos/', 'slug': ''},
            {'image_url': f'{media_url}banners/banner_twcat052.png', 'name': 'Catalítico TWCAT052', 'sku': 'TWCAT052', 'url': '/productos/', 'slug': ''},
            {'image_url': f'{media_url}banners/banner_3x6.png', 'name': 'Tubo flexible 3x6', 'sku': '3x6', 'url': '/productos/', 'slug': ''},
        ]
        featured_products = [{'name': s['name'], 'sku': s['sku'], 'slug': s.get('slug', ''), 'image_url': s['image_url'], 'url': s['url']} for s in hero_slides[:8]]
    # Excluir "flexibles-reforzados" para no duplicar en menú; la raíz "flexibles" lleva a la vista unificada.
    # Excluir "por-clasificar" del menú público.
    header_categories = list(
        Category.objects.filter(
            is_active=True, parent__isnull=True
        ).exclude(slug__in=['flexibles-reforzados', 'por-clasificar']).order_by('name')[:8]
    )
    return render(request, 'core/home_welcome.html', {
        'title': 'Monteazul SPA — Especialistas en repuestos de escape',
        'hero_product_images': hero_slides,
        'header_categories': header_categories,
        'featured_products': featured_products,
    })


def _vehicle_results_context(brand_id, model_id, year, engine_id=None):
    """
    Obtiene productos compatibles para un vehículo. Devuelve dict con products, fitment, brand, model, engine
    o None si los IDs/año son inválidos o no hay marca/modelo.
    """
    if not all([brand_id, model_id, year]):
        return None
    try:
        year = int(year)
    except (ValueError, TypeError):
        return None
    compatibilities = ProductCompatibility.objects.filter(
        brand_id=brand_id,
        model_id=model_id,
        year_from__lte=year,
        year_to__gte=year,
        is_active=True,
    )
    if engine_id:
        compatibilities = compatibilities.filter(engine_id=engine_id)
    product_ids = compatibilities.values_list('product_id', flat=True).distinct()
    products = Product.objects.filter(
        id__in=product_ids,
        is_publishable=True,
        is_active=True,
        deleted_at__isnull=True,
    ).select_related('category').prefetch_related('images', 'compatibilities')
    try:
        brand = VehicleBrand.objects.get(id=brand_id)
        model = VehicleModel.objects.get(id=model_id)
        engine = VehicleEngine.objects.get(id=engine_id) if engine_id else None
    except (VehicleBrand.DoesNotExist, VehicleModel.DoesNotExist, VehicleEngine.DoesNotExist):
        return None
    fitment = {
        'brand': brand.name,
        'model': model.name,
        'year': year,
        'engine': engine.name if engine else None,
    }
    return {
        'products': products,
        'fitment': fitment,
        'count': products.count(),
        'brand': brand,
        'model': model,
        'engine': engine,
    }


def vehicle_search(request):
    """
    Página de búsqueda por vehículo (formulario) y landing de resultados por GET.
    GET con brand, model, year (y opcional engine) → resultados indexables para SEO.
    """
    # Landing indexable: GET con parámetros de vehículo
    brand_id = request.GET.get('brand')
    model_id = request.GET.get('model')
    year = request.GET.get('year')
    engine_id = request.GET.get('engine') or None
    if brand_id and model_id and year:
        ctx = _vehicle_results_context(brand_id, model_id, year, engine_id)
        if ctx is not None:
            fitment = ctx['fitment']
            # Título y descripción por vehículo para SEO
            title_parts = [fitment['brand'], fitment['model'], str(fitment['year'])]
            if fitment.get('engine'):
                title_parts.append(fitment['engine'])
            vehicle_label = ' '.join(title_parts)
            # Snippet orientado a CTR: "Catalíticos para Toyota Yaris 2015" atrae más que "Repuestos de escape para..."
            page_title = f"Catalíticos para {vehicle_label} | Monteazul SPA"
            meta_description = (
                f"Encuentra catalíticos y repuestos compatibles con {vehicle_label}. "
                "Precios y disponibilidad. Envío a todo Chile · Retiro en Macul."
            )
            canonical_url = request.build_absolute_uri(request.get_full_path())
            return render(request, 'core/vehicle_results.html', {
                **ctx,
                'page_title': page_title,
                'meta_description': meta_description,
                'canonical_url': canonical_url,
            })

    # Formulario de búsqueda (sin params o params inválidos)
    brands = VehicleBrand.objects.all().order_by('name')
    categories = Category.objects.filter(is_active=True, parent__isnull=True)[:6]
    from datetime import datetime
    current_year = datetime.now().year
    years = list(range(1980, current_year + 2))
    years.reverse()
    return render(request, 'core/home_public.html', {
        'title': 'Buscar por vehículo',
        'meta_description': (
            'Encuentra catalíticos y repuestos de escape compatibles con tu auto. '
            'Filtra por año, marca y modelo. Toyota, Chevrolet, Nissan, Hyundai y más. Envíos a todo Chile.'
        ),
        'brands': brands,
        'categories': categories,
        'years': years,
    })


@require_http_methods(["GET"])
def api_vehicle_models(request):
    """API: Obtener modelos de una marca"""
    brand_id = request.GET.get('brand_id')
    if not brand_id:
        return JsonResponse({'error': 'brand_id requerido'}, status=400)
    
    models = VehicleModel.objects.filter(brand_id=brand_id).order_by('name')
    data = [{'id': m.id, 'name': m.name} for m in models]
    return JsonResponse({'models': data})


@require_http_methods(["GET"])
def api_vehicle_engines(request):
    """API: Obtener motores de un modelo"""
    model_id = request.GET.get('model_id')
    if not model_id:
        return JsonResponse({'error': 'model_id requerido'}, status=400)
    
    engines = VehicleEngine.objects.filter(model_id=model_id).order_by('name')
    data = [{'id': e.id, 'name': e.name, 'fuel_type': e.fuel_type or ''} for e in engines]
    return JsonResponse({'engines': data})


def validate_vehicle(request):
    """
    POST: valida vehículo y redirige a la URL GET de resultados (landing indexable para SEO).
    Así cada combinación marca/modelo/año tiene una URL única que Google puede indexar.
    """
    if request.method != 'POST':
        return redirect('core:vehicle_search')
    brand_id = request.POST.get('brand')
    model_id = request.POST.get('model')
    year = request.POST.get('year')
    engine_id = request.POST.get('engine') or None
    if not all([brand_id, model_id, year]):
        return redirect('core:vehicle_search')
    try:
        year = int(year)
    except (ValueError, TypeError):
        return redirect('core:vehicle_search')
    # Verificar que existan marca/modelo (y motor si se envió)
    ctx = _vehicle_results_context(brand_id, model_id, year, engine_id)
    if ctx is None:
        return redirect('core:vehicle_search')
    # Guardar en sesión para "modo validado" (carrito, etc.)
    request.session['fitment'] = {
        'brand_id': int(brand_id),
        'model_id': int(model_id),
        'year': year,
        'engine_id': int(engine_id) if engine_id else None,
    }
    # Redirigir a GET para que la página de resultados sea indexable y compartible
    params = {'brand': brand_id, 'model': model_id, 'year': year}
    if engine_id:
        params['engine'] = engine_id
    url = reverse('core:vehicle_search') + '?' + urlencode(params)
    return redirect(url)


@require_http_methods(["GET"])
def api_regiones(request):
    """API: Lista de regiones de Chile."""
    regiones = get_regiones()
    return JsonResponse({"regiones": regiones})


@require_http_methods(["GET"])
def api_comunas(request):
    """API: Comunas filtradas por región (param: region=codigo)."""
    codigo = (request.GET.get("region") or "").strip()
    if not codigo:
        return JsonResponse({"error": "region requerido"}, status=400)
    comunas = get_comunas_por_region(codigo)
    return JsonResponse({"comunas": comunas})


@require_http_methods(["POST"])
def set_location(request):
    """Guarda región y comuna en session para envío. Responde JSON."""
    region = (request.POST.get("region") or "").strip()
    comuna = (request.POST.get("comuna") or "").strip()
    if not region and not comuna:
        return JsonResponse({"saved": False, "error": "Indica al menos región o comuna."}, status=400)
    request.session["shipping_location"] = {
        "region": region or "",
        "comuna": comuna or "",
    }
    request.session.modified = True
    display = ", ".join(filter(None, [comuna or None, region or None])) or "Ubicación guardada"
    return JsonResponse({"saved": True, "display": display})


@require_http_methods(["GET", "POST"])
@ensure_csrf_cookie
def shipping_estimate(request):
    """
    Estima tiempo de llegada según ubicación en session.
    GET/POST: slug (opcional) o product_slug. Responde JSON.
    """
    loc = request.session.get("shipping_location") or {}
    region = loc.get("region", "")
    comuna = loc.get("comuna", "")
    slug = request.GET.get("slug") or request.POST.get("slug") or request.GET.get("product_slug") or ""

    if not comuna and not region:
        return JsonResponse({
            "ok": False,
            "message": "Indica tu ubicación para calcular el envío.",
            "estimate": None,
        })

    # Lógica simplificada: RM 2-3 días, resto 4-6 días hábiles
    if "metropolitana" in (region or "").lower() or "santiago" in (comuna or "").lower() or "providencia" in (comuna or "").lower():
        estimate = "2-3 días hábiles"
    else:
        estimate = "4-6 días hábiles"
    location_display = ", ".join(filter(None, [comuna, region]))

    return JsonResponse({
        "ok": True,
        "estimate": estimate,
        "location": location_display,
        "message": f"Llegada estimada a {location_display}: {estimate}",
    })


def page_404(request, exception=None):
    """Página 404 personalizada con diseño coherente al sitio."""
    return render(request, "404.html", status=404)


def page_500(request):
    """Página 500 personalizada."""
    return render(request, "500.html", status=500)


