from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from django.http import JsonResponse, HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from django.db.models import Q


@dataclass
class Fitment:
    brand: str = ""
    model: str = ""
    year: str = ""
    engine: str = ""


@require_GET
def home_public(request: HttpRequest) -> HttpResponse:
    # Importamos desde catalog si existe, sin romper si el proyecto aún no tiene todo conectado.
    brands = []
    years = list(range(2026, 1979, -1))  # 1980..2026 (ajusta si necesitas)
    try:
        from catalog.models import VehicleBrand  # type: ignore
        brands = VehicleBrand.objects.all().order_by("name")
    except Exception:
        brands = []

    ctx = {
        "title": "Bienvenida",
        "brands": brands,
        "years": years,
        # opcional: desde settings o context processor
        "whatsapp_number": getattr(request, "whatsapp_number", None),
    }
    return render(request, "core/home_public.html", ctx)


@require_GET
def home(request: HttpRequest) -> HttpResponse:
    return render(request, "core/home.html", {"title": "Inicio"})


@require_GET
def api_modelos(request: HttpRequest) -> JsonResponse:
    """Devuelve modelos para una marca.
    Respuesta:
      {"models": [{"id": 1, "name": "Corolla"}, ...]}
    """
    brand_id = request.GET.get("brand_id")
    if not brand_id:
        return JsonResponse({"models": []})

    try:
        from catalog.models import VehicleModel  # type: ignore
        qs = VehicleModel.objects.filter(brand_id=brand_id).order_by("name")
        return JsonResponse({"models": [{"id": m.id, "name": str(getattr(m, "name", m))} for m in qs]})
    except Exception:
        return JsonResponse({"models": []})


@require_GET
def api_motores(request: HttpRequest) -> JsonResponse:
    """Devuelve motores para un modelo.
    Respuesta:
      {"engines": [{"id": 1, "name": "2.0"}, ...]}
    """
    model_id = request.GET.get("model_id")
    if not model_id:
        return JsonResponse({"engines": []})

    try:
        from catalog.models import VehicleEngine  # type: ignore
        qs = VehicleEngine.objects.filter(model_id=model_id).order_by("name")
        return JsonResponse({"engines": [{"id": e.id, "name": str(getattr(e, "name", e))} for e in qs]})
    except Exception:
        return JsonResponse({"engines": []})


@require_GET
def vehicle_results(request: HttpRequest) -> HttpResponse:
    """Resultados de compatibilidad.
    Espera querystring: brand, model, year, engine (IDs o valores).
    """
    brand = request.GET.get("brand", "")
    model = request.GET.get("model", "")
    year = request.GET.get("year", "")
    engine = request.GET.get("engine", "")

    fitment = Fitment()
    # Resolución de nombres “humanos”
    try:
        from catalog.models import VehicleBrand, VehicleModel, VehicleEngine  # type: ignore
        if brand:
            b = VehicleBrand.objects.filter(id=brand).first()
            fitment.brand = getattr(b, "name", "") if b else str(brand)
        if model:
            m = VehicleModel.objects.filter(id=model).first()
            fitment.model = getattr(m, "name", "") if m else str(model)
        if engine:
            e = VehicleEngine.objects.filter(id=engine).first()
            fitment.engine = getattr(e, "name", "") if e else str(engine)
        fitment.year = str(year)
    except Exception:
        fitment = Fitment(brand=str(brand), model=str(model), year=str(year), engine=str(engine))

    products = []
    count = 0

    # Intento 1: Si existe un modelo tipo ProductFitment (lo más común)
    try:
        from catalog.models import Product, ProductFitment  # type: ignore
        # Asumimos campos: product FK, brand/model/engine FK, year_from/year_to opcionales
        q = Q()
        if brand:
            q &= Q(brand_id=brand) | Q(model__brand_id=brand)
        if model:
            q &= Q(model_id=model)
        if engine:
            q &= Q(engine_id=engine)
        if year and year.isdigit():
            y = int(year)
            q &= (Q(year_from__isnull=True) | Q(year_from__lte=y)) & (Q(year_to__isnull=True) | Q(year_to__gte=y))

        fit_qs = ProductFitment.objects.filter(q).select_related("product")[:120]
        products = [pf.product for pf in fit_qs if pf.product]
        count = len(products)
    except Exception:
        # Intento 2: compatibilidad simple con M2M (si tu Product tiene relaciones)
        try:
            from catalog.models import Product  # type: ignore
            qs = Product.objects.all()
            if model:
                # Si existe m2m models, esto funciona; si no, cae al except.
                qs = qs.filter(models__id=model)
            products = list(qs.distinct()[:120])
            count = len(products)
        except Exception:
            products = []
            count = 0

    ctx = {"fitment": fitment, "products": products, "count": count}
    return render(request, "core/vehicle_results.html", ctx)
