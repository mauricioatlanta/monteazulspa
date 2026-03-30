from django.shortcuts import render
from django.http import JsonResponse

from apps.catalog.models import (
    VehicleBrand,
    VehicleModel,
    VehicleEngine,
)
from apps.catalog.services.vehicle_search_result_builder import build_vehicle_result_context


def vehicle_search_page(request):
    brands = VehicleBrand.objects.order_by("name")
    selected_brand_id = request.GET.get("brand_id", "").strip()
    selected_model_id = request.GET.get("model_id", "").strip()
    selected_engine_id = request.GET.get("engine_id", "").strip()
    selected_year = request.GET.get("year", "").strip()
    initial_q = request.GET.get("q", "").strip()

    initial_models = []
    initial_engines = []

    if selected_model_id and selected_model_id.isdigit() and not (selected_brand_id and selected_brand_id.isdigit()):
        try:
            model = VehicleModel.objects.filter(id=int(selected_model_id)).select_related("brand").first()
            if model:
                selected_brand_id = str(model.brand_id)
                initial_models = list(
                    VehicleModel.objects.filter(brand_id=model.brand_id)
                    .order_by("name")
                    .values("id", "name")
                )
        except (ValueError, TypeError):
            pass
    elif selected_brand_id and selected_brand_id.isdigit():
        initial_models = list(
            VehicleModel.objects.filter(brand_id=int(selected_brand_id))
            .order_by("name")
            .values("id", "name")
        )

    if selected_model_id and selected_model_id.isdigit():
        initial_engines = [
            {
                "id": e.id,
                "name": e.name,
                "fuel_type": e.fuel_type or "",
                "displacement_cc": e.displacement_cc,
            }
            for e in VehicleEngine.objects.filter(model_id=int(selected_model_id)).order_by("displacement_cc", "name")
        ]

    return render(request, "catalog/vehicle_search.html", {
        "brands": brands,
        "selected_brand_id": selected_brand_id,
        "selected_model_id": selected_model_id,
        "selected_engine_id": selected_engine_id,
        "selected_year": selected_year,
        "initial_q": initial_q,
        "initial_models": initial_models,
        "initial_engines": initial_engines,
    })


def vehicle_models_api(request):
    brand_id = request.GET.get("brand_id")
    if not brand_id:
        return JsonResponse({"results": []})

    models = VehicleModel.objects.filter(brand_id=brand_id).order_by("name")
    return JsonResponse({
        "results": [{"id": m.id, "name": m.name} for m in models]
    })


def vehicle_engines_api(request):
    model_id = request.GET.get("model_id")
    if not model_id:
        return JsonResponse({"results": []})

    engines = VehicleEngine.objects.filter(model_id=model_id).order_by("displacement_cc", "name")
    return JsonResponse({
        "results": [
            {
                "id": e.id,
                "name": e.name,
                "fuel_type": e.fuel_type or "",
                "displacement_cc": e.displacement_cc,
            }
            for e in engines
        ]
    })


def _product_payload(p):
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "category": p.category.name if p.category else "",
        "url": p.get_absolute_url() if hasattr(p, "get_absolute_url") else "",
    }


def vehicle_products_api(request):
    """
    Devuelve productos por vehículo usando el mismo motor que la vista y el test de integridad.
    - verified: compatibilidad exacta (model no nulo).
    - suggested_brand_wide: compatibilidad por marca (model=None), filtro y ranking técnico.
    - suggested_other: otras sugerencias técnicas (get_vehicle_suggested_products_v2).
    - suggested: suggested_brand_wide + suggested_other (compatibilidad frontend).
    - results: verified + suggested.
    """
    brand_id = request.GET.get("brand_id")
    model_id = request.GET.get("model_id")
    engine_id = request.GET.get("engine_id")
    year = request.GET.get("year")
    fuel_type = (request.GET.get("fuel_type") or "").strip() or None
    displacement_raw = (request.GET.get("displacement_cc") or "").strip()

    if not brand_id or not model_id or not year:
        return JsonResponse({
            "verified": [],
            "suggested": [],
            "suggested_brand_wide": [],
            "suggested_other": [],
            "results": [],
        })

    try:
        year_int = int(year)
    except ValueError:
        return JsonResponse({
            "verified": [],
            "suggested": [],
            "suggested_brand_wide": [],
            "suggested_other": [],
            "results": [],
        })

    engine_id_int = None
    if engine_id:
        try:
            engine_id_int = int(engine_id)
        except ValueError:
            pass

    displacement_cc = None
    if displacement_raw:
        try:
            displacement_cc = int(displacement_raw)
        except ValueError:
            pass

    ctx = build_vehicle_result_context(
        brand_id=int(brand_id),
        model_id=int(model_id),
        year=year_int,
        engine_id=engine_id_int,
        fuel_type=fuel_type,
        displacement_cc=displacement_cc,
    )

    if ctx is None:
        return JsonResponse({
            "verified": [],
            "suggested": [],
            "suggested_brand_wide": [],
            "suggested_other": [],
            "results": [],
        })

    products_verified = ctx["products_verified"]
    products_suggested_brand_wide = ctx["products_suggested_brand_wide"]
    products_suggested_other = ctx["products_suggested_other"]

    verified_payload = [_product_payload(p) for p in products_verified]
    brand_wide_payload = [_product_payload(p) for p in products_suggested_brand_wide]
    other_payload = [_product_payload(p) for p in products_suggested_other]
    suggested_payload = brand_wide_payload + other_payload
    results = verified_payload + suggested_payload

    return JsonResponse({
        "verified": verified_payload,
        "suggested": suggested_payload,
        "suggested_brand_wide": brand_wide_payload,
        "suggested_other": other_payload,
        "results": results,
    })
