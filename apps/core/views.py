from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.catalog.models import Category, Product, VehicleBrand, VehicleModel, VehicleEngine, ProductCompatibility


def home(request):
    """Página de bienvenida al sitio monteazulspa.cl"""
    return render(request, 'core/home_welcome.html', {
        'title': 'Bienvenida | Monteazul SPA',
    })


def vehicle_search(request):
    """Página de búsqueda por tipo de vehículo (año, marca, modelo, motor)."""
    brands = VehicleBrand.objects.all().order_by('name')
    categories = Category.objects.filter(is_active=True, parent__isnull=True)[:6]
    from datetime import datetime
    current_year = datetime.now().year
    years = list(range(1980, current_year + 2))
    years.reverse()
    return render(request, 'core/home_public.html', {
        'title': 'Buscar por vehículo | Monteazul SPA',
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
    """Validar vehículo y mostrar productos compatibles"""
    if request.method == 'POST':
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
        
        # Buscar productos compatibles
        compatibilities = ProductCompatibility.objects.filter(
            brand_id=brand_id,
            model_id=model_id,
            year_from__lte=year,
            year_to__gte=year,
            is_active=True
        )
        
        if engine_id:
            compatibilities = compatibilities.filter(engine_id=engine_id)
        
        # Obtener productos únicos y publicables
        product_ids = compatibilities.values_list('product_id', flat=True).distinct()
        products = Product.objects.filter(
            id__in=product_ids,
            is_publishable=True,
            is_active=True,
            deleted_at__isnull=True
        ).select_related('category').prefetch_related('images', 'compatibilities')
        
        # Guardar en sesión para "modo validado"
        request.session['fitment'] = {
            'brand_id': int(brand_id),
            'model_id': int(model_id),
            'year': year,
            'engine_id': int(engine_id) if engine_id else None,
        }
        
        # Obtener nombres para mostrar
        brand = VehicleBrand.objects.get(id=brand_id)
        model = VehicleModel.objects.get(id=model_id)
        engine = VehicleEngine.objects.get(id=engine_id) if engine_id else None
        
        context = {
            'products': products,
            'fitment': {
                'brand': brand.name,
                'model': model.name,
                'year': year,
                'engine': engine.name if engine else None,
            },
            'count': products.count(),
        }
        
        return render(request, 'core/vehicle_results.html', context)
    
    return redirect('core:vehicle_search')
