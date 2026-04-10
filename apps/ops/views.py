import json
from datetime import datetime, timedelta
from decimal import Decimal
from django.conf import settings
from django.db.models import Sum, Count, Q, F, Case, When, IntegerField
from django.db.models.functions import Coalesce, TruncDate
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils import timezone
from django.views.generic import ListView, DetailView

from django.contrib import messages
from django.core.paginator import Paginator
from django.views.decorators.http import require_http_methods, require_POST

from apps.orders.models import Order, OrderItem, OrderStatus, WarrantyClaim, WarrantyClaimStatus

# Estados que cuentan como venta real/cobrada (alineado con margen)
REAL_SALES_STATUSES = [
    OrderStatus.PAID,
    OrderStatus.PREPARATION,
    OrderStatus.SHIPPED,
    OrderStatus.COMPLETED,
]
from apps.customers.models import CustomerProfile
from apps.catalog.models import Product, Category, ProductViewStat
from apps.catalog.forms import ProductAdminForm, ProductImageFormSet
from apps.catalog.views import (
    _get_descendant_category_ids,
    _apply_category_filter,
    _smart_search_queryset,
    order_products_for_display,
)

# Categorías flexibles: ordenar por medida (diámetro x largo, menor a mayor pulgada)
FLEXIBLES_CAT_SLUGS = ("flexibles", "flexibles-normales", "flexibles-con-extension")
from apps.inventory.models import StockMovement
from apps.audit.models import AuditLog

from .decorators import ops_required, owner_only, catalog_admin_required


# --- Dashboard ---

def _month_start_end_for_date(d):
    """Devuelve (start_dt, end_dt) timezone-aware para el mes de la fecha d."""
    start_dt = timezone.make_aware(datetime(d.year, d.month, 1, 0, 0, 0))
    if d.month == 12:
        end_dt = timezone.make_aware(datetime(d.year + 1, 1, 1, 0, 0, 0))
    else:
        end_dt = timezone.make_aware(datetime(d.year, d.month + 1, 1, 0, 0, 0))
    return start_dt, end_dt


@ops_required
def seo_dashboard(request):
    """Dashboard SEO interno: productos más vistos (vistas por sesión, sin terceros)."""
    top_productos = (
        ProductViewStat.objects.select_related("product")
        .order_by("-views")[:50]
    )
    max_views = top_productos[0].views if top_productos else 0
    return render(
        request,
        "ops/seo_dashboard.html",
        {"top_productos": top_productos, "max_views": max_views},
    )


@ops_required
def dashboard(request):
    now = timezone.now()
    today = now.date()
    start_of_month = today.replace(day=1)
    start_dt, end_dt = _month_start_end_for_date(today)
    today_start = timezone.make_aware(datetime(today.year, today.month, today.day, 0, 0, 0))
    today_end = today_start + timedelta(days=1)

    # Ventas hoy (cobradas)
    orders_today = Order.objects.filter(
        created_at__gte=today_start,
        created_at__lt=today_end,
        status__in=REAL_SALES_STATUSES,
    )
    sales_today = orders_today.aggregate(s=Sum("total"))["s"] or Decimal("0")

    # Ventas del mes (cobradas) — mismo criterio que margen
    orders_month = Order.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
        status__in=REAL_SALES_STATUSES,
    )
    sales_month = orders_month.aggregate(s=Sum("total"))["s"] or Decimal("0")

    # Margen real (ventas - costo snapshot de items)
    items_month = OrderItem.objects.filter(
        order__created_at__gte=start_dt,
        order__created_at__lt=end_dt,
        order__status__in=REAL_SALES_STATUSES,
    )
    revenue = items_month.aggregate(s=Sum(F("unit_price_applied") * F("quantity") - F("discount_amount_applied")))["s"] or Decimal("0")
    cost = items_month.aggregate(s=Sum(F("cost_price_snapshot") * F("quantity")))["s"] or Decimal("0")
    margin = revenue - cost

    low_stock = Product.objects.filter(
        is_active=True,
        stock__lte=F("stock_minimum_alert"),
        stock_minimum_alert__gt=0,
    ).order_by("stock")[:15]

    warranty_open = WarrantyClaim.objects.filter(status=WarrantyClaimStatus.OPEN).count()
    warranty_expired_items = OrderItem.objects.filter(
        warranty_expiration_date__lt=today,
        warranty_expiration_date__isnull=False,
    ).count()

    recent_orders = Order.objects.all().order_by("-created_at")[:10]
    recent_audit = AuditLog.objects.all()[:8]

    return render(request, "ops/dashboard.html", {
        "sales_today": sales_today,
        "sales_month": sales_month,
        "margin": margin,
        "revenue": revenue,
        "low_stock": low_stock,
        "warranty_open": warranty_open,
        "warranty_expired_items": warranty_expired_items,
        "recent_orders": recent_orders,
        "recent_audit": recent_audit,
    })


# --- Ventas ---

@ops_required
def sales_list(request):
    now = timezone.now()
    today = now.date()
    start_dt, end_dt = _month_start_end_for_date(today)
    today_start = timezone.make_aware(datetime(today.year, today.month, today.day, 0, 0, 0))
    today_end = today_start + timedelta(days=1)
    thirty_days_ago = today - timedelta(days=30)
    thirty_days_ago_dt = timezone.make_aware(datetime(thirty_days_ago.year, thirty_days_ago.month, thirty_days_ago.day, 0, 0, 0))

    # KPIs: ventas hoy y mes (cobradas)
    sales_today = (
        Order.objects.filter(
            created_at__gte=today_start,
            created_at__lt=today_end,
            status__in=REAL_SALES_STATUSES,
        ).aggregate(s=Sum("total"))["s"]
        or Decimal("0")
    )
    sales_month = (
        Order.objects.filter(
            created_at__gte=start_dt,
            created_at__lt=end_dt,
            status__in=REAL_SALES_STATUSES,
        ).aggregate(s=Sum("total"))["s"]
        or Decimal("0")
    )
    total_real_sales = (
        Order.objects.filter(status__in=REAL_SALES_STATUSES).aggregate(s=Sum("total"))["s"]
        or Decimal("0")
    )
    orders_count_real = Order.objects.filter(status__in=REAL_SALES_STATUSES).count()
    orders_pending = Order.objects.filter(status=OrderStatus.PENDING).count()
    orders_cancelled = Order.objects.filter(status=OrderStatus.CANCELLED).count()

    # Gráfico: ventas por día últimos 30 días (solo cobradas)
    daily_sales = (
        Order.objects.filter(
            created_at__gte=thirty_days_ago_dt,
            status__in=REAL_SALES_STATUSES,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(total=Sum("total"))
        .order_by("day")
    )
    # Rellenar días sin ventas con 0 para el gráfico
    day_totals = {d["day"]: float(d["total"]) for d in daily_sales}
    chart_labels_30d = []
    chart_data_30d = []
    for i in range(30):
        d = thirty_days_ago + timedelta(days=i)
        chart_labels_30d.append(d.strftime("%d/%m"))
        chart_data_30d.append(day_totals.get(d, 0.0))

    # Gráfico: órdenes por estado
    status_counts = (
        Order.objects.values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    status_labels = dict(OrderStatus.choices)
    chart_status_labels = [status_labels.get(s["status"], s["status"]) for s in status_counts]
    chart_status_data = [s["count"] for s in status_counts]
    chart_status_colors = [
        "#22c55e",   # PAID/COMPLETED - green
        "#06b6d4",   # PREPARATION/SHIPPED - cyan
        "#eab308",   # PENDING - yellow
        "#ef4444",   # CANCELLED - red
        "#8b5cf6",   # extra
        "#64748b",
    ][: len(chart_status_labels)]

    # Listado: filtro por estado y paginación
    qs = Order.objects.all().select_related("customer").order_by("-created_at")
    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)
    search_q = request.GET.get("q", "").strip()
    if search_q:
        if search_q.isdigit():
            qs = qs.filter(pk=int(search_q))
        else:
            qs = qs.filter(
                Q(customer__user__email__icontains=search_q)
                | Q(customer__company_name__icontains=search_q)
                | Q(customer__user__first_name__icontains=search_q)
                | Q(customer__user__last_name__icontains=search_q)
            )
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page", 1)
    try:
        page = paginator.page(int(page_number))
    except (ValueError, TypeError):
        page = paginator.page(1)
    orders = page

    return render(
        request,
        "ops/sales_list.html",
        {
            "orders": orders,
            "order_status_choices": OrderStatus.choices,
            "sales_today": sales_today,
            "sales_month": sales_month,
            "total_real_sales": total_real_sales,
            "orders_count_real": orders_count_real,
            "orders_pending": orders_pending,
            "orders_cancelled": orders_cancelled,
            "chart_labels_30d": json.dumps(chart_labels_30d),
            "chart_data_30d": json.dumps(chart_data_30d),
            "chart_status_labels": json.dumps(chart_status_labels),
            "chart_status_data": json.dumps(chart_status_data),
            "chart_status_colors": json.dumps(chart_status_colors),
            "status_filter": status_filter,
            "search_q": search_q,
        },
    )


@ops_required
def sales_detail(request, pk):
    order = get_object_or_404(Order.objects.select_related("customer"), pk=pk)
    return render(request, "ops/sales_detail.html", {"order": order})


@ops_required
def sales_cancel(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == "POST":
        reason = request.POST.get("cancel_reason", "").strip()
        if not reason:
            from django.contrib import messages
            messages.error(request, "Debes indicar el motivo de anulación.")
            return redirect("ops:sales_detail", pk=pk)
        order.status = OrderStatus.CANCELLED
        order.cancelled_at = timezone.now()
        order.cancel_reason = reason
        order.save(update_fields=["status", "cancelled_at", "cancel_reason", "updated_at"])
        AuditLog.objects.create(
            user=request.user,
            action="ORDER_CANCELLED",
            model="orders.Order",
            object_id=str(order.pk),
            description=f"Orden #{order.pk} anulada. Motivo: {reason}",
        )
        from django.contrib import messages
        messages.success(request, "Orden anulada correctamente.")
        return redirect("ops:sales_detail", pk=pk)
    return redirect("ops:sales_detail", pk=pk)


# --- Inventario ---

def _inventory_intcomma(n):
    """Formato numérico para KPIs de inventario (miles con coma)."""
    return f"{int(round(float(n))):,}"


@ops_required
def inventory_list(request):
    base_products = Product.objects.filter(
        is_active=True, deleted_at__isnull=True
    ).select_related("category")
    products = base_products.order_by("sku")

    # KPIs globales (siempre sobre el inventario completo)
    total_skus = base_products.count()
    inventory_valorized = (
        base_products.filter(stock__gt=0)
        .annotate(valor=F("stock") * Coalesce(F("cost_price"), Decimal("0")))
        .aggregate(s=Sum("valor"))["s"]
        or Decimal("0")
    )
    low_stock_count = base_products.filter(
        stock__lte=F("stock_minimum_alert"), stock_minimum_alert__gt=0
    ).count()
    recent_movements = (
        StockMovement.objects.select_related("product", "related_order", "created_by")
        .order_by("-created_at")[:14]
    )

    low = request.GET.get("low")
    no_move_days = request.GET.get("no_move")
    no_move_days_val = None
    if low:
        products = products.filter(
            stock__lte=F("stock_minimum_alert"), stock_minimum_alert__gt=0
        )
    elif no_move_days:
        try:
            days = int(no_move_days)
            days = min(max(days, 1), 365)
        except (ValueError, TypeError):
            days = 60
        no_move_days_val = days
        since_dt = timezone.now() - timedelta(days=days)
        product_ids_with_movement = (
            StockMovement.objects.filter(created_at__gte=since_dt)
            .values_list("product_id", flat=True)
            .distinct()
        )
        products = products.exclude(pk__in=product_ids_with_movement).filter(
            stock__gt=0
        )
    # Monto inmovilizado y valor por producto (cuando filtro no_move)
    immobilized_value = None
    if no_move_days_val is not None:
        products = products.annotate(
            valor_costo=F("stock") * Coalesce(F("cost_price"), Decimal("0"))
        )
        immobilized_value = (
            products.aggregate(s=Sum("valor_costo"))["s"] or Decimal("0")
        )

    return render(
        request,
        "ops/inventory_list.html",
        {
            "products": products,
            "no_move_days": no_move_days_val,
            "low_filter": bool(low),
            "immobilized_value": immobilized_value,
            "total_skus": total_skus,
            "inventory_valorized": inventory_valorized,
            "inventory_valorized_display": _inventory_intcomma(inventory_valorized),
            "low_stock_count": low_stock_count,
            "recent_movements": recent_movements,
        },
    )


@ops_required
def inventory_movements(request, product_id=None):
    qs = StockMovement.objects.select_related("product", "related_order", "created_by").order_by("-created_at")
    if product_id:
        qs = qs.filter(product_id=product_id)
    return render(request, "ops/inventory_movements.html", {"movements": qs[:100], "product_id": product_id})


# --- Clientes ---

@ops_required
def customers_list(request):
    qs = CustomerProfile.objects.all().select_related("user").order_by("-updated_at")
    tipo = request.GET.get("tipo")
    if tipo and tipo in dict(CustomerProfile.CustomerType.choices):
        qs = qs.filter(customer_type=tipo)
    return render(request, "ops/customers_list.html", {
        "customers": qs,
        "customer_type_choices": CustomerProfile.CustomerType.choices,
    })


@ops_required
def customers_detail(request, pk):
    customer = get_object_or_404(CustomerProfile.objects.select_related("user"), pk=pk)
    orders = customer.orders.all().order_by("-created_at")[:50]
    return render(request, "ops/customers_detail.html", {"customer": customer, "orders": orders})


# --- Garantías ---

@ops_required
def warranties_list(request):
    status_filter = request.GET.get("status")
    qs = WarrantyClaim.objects.select_related(
        "order_item__order", "order_item__product", "customer"
    ).order_by("-created_at")
    if status_filter and status_filter in dict(WarrantyClaimStatus.choices):
        qs = qs.filter(status=status_filter)
    return render(request, "ops/warranties_list.html", {
        "claims": qs,
        "warranty_status_choices": WarrantyClaimStatus.choices,
    })


@ops_required
def warranties_detail(request, pk):
    claim = get_object_or_404(
        WarrantyClaim.objects.select_related(
            "order_item__order", "order_item__product", "customer"
        ),
        pk=pk,
    )
    return render(request, "ops/warranties_detail.html", {"claim": claim})


# --- Reportes ---

def _active_date_chip(date_from, date_to, today):
    """Determina qué chip de la barra de fechas debe ir active según from/to."""
    if not date_from or not date_to:
        return "month"
    if date_from == date_to == today:
        return "today"
    last_7 = today - timedelta(days=6)
    if date_from == last_7 and date_to == today:
        return "7d"
    start_of_month = today.replace(day=1)
    if date_from == start_of_month and date_to == today:
        return "month"
    if date_from == date_from.replace(month=1, day=1) and date_to == today:
        return "year"
    return None


@ops_required
def reports_index(request):
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    last_7 = today - timedelta(days=6)

    # Filtro de fechas opcional por GET (para KPIs y barra active)
    date_from_s = request.GET.get("from")
    date_to_s = request.GET.get("to")
    try:
        date_from = datetime.strptime(date_from_s, "%Y-%m-%d").date() if date_from_s else start_of_month
    except (ValueError, TypeError):
        date_from = start_of_month
    try:
        date_to = datetime.strptime(date_to_s, "%Y-%m-%d").date() if date_to_s else today
    except (ValueError, TypeError):
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    start_dt = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(date_to, datetime.min.time())) + timedelta(days=1)

    # Ventas del período (cobradas) — mismo criterio que margen
    orders_month = Order.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
        status__in=REAL_SALES_STATUSES,
    )
    sales_month = orders_month.aggregate(s=Sum("total"))["s"] or Decimal("0")

    # Inventario valorizado (costo): solo productos con stock > 0
    from django.db.models.functions import Coalesce
    inventory_valorized = (
        Product.objects.filter(
            is_active=True,
            deleted_at__isnull=True,
            stock__gt=0,
        )
        .annotate(valor=F("stock") * Coalesce(F("cost_price"), Decimal("0")))
        .aggregate(s=Sum("valor"))["s"]
        or Decimal("0")
    )

    # Margen y utilidad del período (mismo rango y estados)
    items_month = OrderItem.objects.filter(
        order__created_at__gte=start_dt,
        order__created_at__lt=end_dt,
        order__status__in=REAL_SALES_STATUSES,
    )
    revenue = items_month.aggregate(
        s=Sum(F("unit_price_applied") * F("quantity") - F("discount_amount_applied"))
    )["s"] or Decimal("0")
    cost = items_month.aggregate(
        s=Sum(F("cost_price_snapshot") * F("quantity"))
    )["s"] or Decimal("0")
    margin_month = revenue - cost
    margin_pct = (margin_month / revenue * 100) if revenue else Decimal("0")

    # Crecimiento % vs mes anterior (ventas cobradas)
    prev_month_end = start_of_month - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    prev_start_dt = timezone.make_aware(datetime.combine(prev_month_start, datetime.min.time()))
    prev_end_dt = timezone.make_aware(datetime.combine(prev_month_end, datetime.min.time())) + timedelta(days=1)
    sales_prev = (
        Order.objects.filter(
            created_at__gte=prev_start_dt,
            created_at__lt=prev_end_dt,
            status__in=REAL_SALES_STATUSES,
        )
        .aggregate(s=Sum("total"))["s"]
        or Decimal("0")
    )
    growth_pct = (
        ((sales_month - sales_prev) / sales_prev * 100) if sales_prev else Decimal("0")
    )

    # Margen mes anterior (para alertas predictivas)
    items_prev = OrderItem.objects.filter(
        order__created_at__gte=prev_start_dt,
        order__created_at__lt=prev_end_dt,
        order__status__in=REAL_SALES_STATUSES,
    )
    rev_prev = items_prev.aggregate(
        s=Sum(F("unit_price_applied") * F("quantity") - F("discount_amount_applied"))
    )["s"] or Decimal("0")
    cost_prev = items_prev.aggregate(s=Sum(F("cost_price_snapshot") * F("quantity")))["s"] or Decimal("0")
    margen_prev_pct = (rev_prev - cost_prev) / rev_prev * 100 if rev_prev else Decimal("0")
    margin_mom_delta_pct = round(float(margin_pct - margen_prev_pct), 1)

    # Config para margen mínimo recomendado (alertas)
    from apps.ops.models import ConfiguracionEmpresa
    config = ConfiguracionEmpresa.get_singleton()
    margen_min = float(config.margen_minimo_recomendado or 15)

    # Líneas vendidas bajo margen mínimo en el período (solo usamos campos de item, no order)
    margin_below_min_count = 0
    for item in items_month.only(
        "unit_price_applied", "quantity", "discount_amount_applied", "cost_price_snapshot"
    )[:500]:
        line_rev = item.unit_price_applied * item.quantity - item.discount_amount_applied
        line_cost = item.cost_price_snapshot * item.quantity
        if line_rev <= 0:
            continue
        line_margin_pct = (line_rev - line_cost) / line_rev * 100
        if line_margin_pct < margen_min:
            margin_below_min_count += 1

    # Alertas estratégicas (predictivas) para el Centro de Inteligencia
    strategic_alerts = []
    if margin_mom_delta_pct < -2 and float(margin_pct) < margen_min:
        strategic_alerts.append({
            "level": "danger",
            "message": f"Tu margen promedio cayó {abs(margin_mom_delta_pct)}% este mes y está bajo el mínimo recomendado ({margen_min:.0f}%).",
        })
    elif margin_mom_delta_pct < -2:
        strategic_alerts.append({
            "level": "warning",
            "message": f"Tu margen promedio cayó {abs(margin_mom_delta_pct)}% este mes.",
        })
    if margin_below_min_count > 0:
        strategic_alerts.append({
            "level": "danger" if margin_below_min_count >= 3 else "warning",
            "message": f"Has vendido {margin_below_min_count} línea(s) bajo margen mínimo recomendado ({margen_min:.0f}%).",
        })

    active_chip = _active_date_chip(date_from, date_to, today)

    # Formateo con separador de miles (evita depender de django.contrib.humanize en el template)
    def _intcomma(n):
        return f"{int(round(float(n))):,}"

    return render(
        request,
        "ops/reports_index.html",
        {
            "sales_month": sales_month,
            "sales_prev_month": sales_prev,
            "inventory_valorized": inventory_valorized,
            "margin_pct": margin_pct,
            "margin_month": margin_month,
            "growth_pct": growth_pct,
            "margin_mom_delta_pct": margin_mom_delta_pct,
            "margen_minimo_recomendado": margen_min,
            "margin_below_min_count": margin_below_min_count,
            "strategic_alerts": strategic_alerts,
            "date_from": date_from,
            "date_to": date_to,
            "today": today,
            "date_7d_ago": last_7,
            "active_date_chip": active_chip,
            "sales_month_display": _intcomma(sales_month),
            "sales_prev_month_display": _intcomma(sales_prev),
            "inventory_valorized_display": _intcomma(inventory_valorized),
            "margin_month_display": _intcomma(margin_month),
        },
    )


@ops_required
def reports_sales(request):
    from csv import writer as csv_writer
    from io import StringIO

    today = timezone.now().date()
    date_from_s = request.GET.get("from") or today.replace(day=1).isoformat()
    date_to_s = request.GET.get("to") or today.isoformat()
    try:
        date_from = datetime.strptime(date_from_s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        date_from = today.replace(day=1)
    try:
        date_to = datetime.strptime(date_to_s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        date_to = today
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    start_dt = timezone.make_aware(datetime.combine(date_from, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(date_to, datetime.min.time())) + timedelta(days=1)

    orders = Order.objects.filter(
        created_at__gte=start_dt,
        created_at__lt=end_dt,
    ).exclude(status=OrderStatus.CANCELLED).select_related("customer").order_by("created_at")

    if request.GET.get("export") == "csv":
        buf = StringIO()
        w = csv_writer(buf)
        w.writerow(["ID", "Fecha", "Cliente", "Estado", "Subtotal", "Descuento", "Impuesto", "Total"])
        for o in orders:
            # Montos en CLP como enteros (nivel contable)
            w.writerow([
                o.pk,
                o.created_at.strftime("%Y-%m-%d %H:%M"),
                str(o.customer),
                o.get_status_display(),
                int(o.subtotal),
                int(o.discount_total),
                int(o.tax_total),
                int(o.total),
            ])
        content = "\ufeff" + buf.getvalue()
        resp = HttpResponse(content, content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = 'attachment; filename="ventas_{}_{}.csv"'.format(date_from, date_to)
        return resp

    total = orders.aggregate(s=Sum("total"))["s"] or Decimal("0")
    return render(request, "ops/reports_sales.html", {
        "orders": orders,
        "date_from": date_from,
        "date_to": date_to,
        "total": total,
    })


# --- Centro Estratégico (solo OWNER) ---

def _exposure_for_days(days):
    """Devuelve (exposicion, label, risk_pct 0-100) para N días de garantía."""
    if days <= 10:
        return "low", "Baja exposición", 25
    if days <= 30:
        return "medium", "Exposición media", 35 + min(30, (days - 10))
    return "high", "Alta exposición", min(95, 65 + (days - 30) // 10)


def _settings_metrics_and_recommendations():
    """Métricas y recomendaciones para el Centro Estratégico (Cockpit Estratégico v2)."""
    from apps.ops.models import ConfiguracionEmpresa
    from collections import Counter

    now = timezone.now()
    start_dt, end_dt = _month_start_end_for_date(now.date())
    start_prev = start_dt - timedelta(days=32)
    start_prev = timezone.make_aware(datetime(start_prev.year, start_prev.month, 1, 0, 0, 0))

    # Margen del mes
    items_month = OrderItem.objects.filter(
        order__created_at__gte=start_dt,
        order__created_at__lt=end_dt,
        order__status__in=REAL_SALES_STATUSES,
    )
    revenue = items_month.aggregate(
        s=Sum(F("unit_price_applied") * F("quantity") - F("discount_amount_applied"))
    )["s"] or Decimal("0")
    cost = items_month.aggregate(s=Sum(F("cost_price_snapshot") * F("quantity")))["s"] or Decimal("0")
    margin = revenue - cost
    margen_pct = (margin / revenue * 100) if revenue else Decimal("0")

    # Margen mes anterior (para MoM y alertas)
    items_prev = OrderItem.objects.filter(
        order__created_at__gte=start_prev,
        order__created_at__lt=start_dt,
        order__status__in=REAL_SALES_STATUSES,
    )
    rev_prev = items_prev.aggregate(
        s=Sum(F("unit_price_applied") * F("quantity") - F("discount_amount_applied"))
    )["s"] or Decimal("0")
    cost_prev = items_prev.aggregate(s=Sum(F("cost_price_snapshot") * F("quantity")))["s"] or Decimal("0")
    margen_prev = (rev_prev - cost_prev) / rev_prev * 100 if rev_prev else Decimal("0")
    margin_mom_delta_pct = round(float(margen_pct - margen_prev), 1)

    # Items vendidos este mes (para tasa de reclamos)
    items_sold_count = items_month.aggregate(c=Count("id"))["c"] or 0

    # Reclamos este mes vs anterior
    claims_this = WarrantyClaim.objects.filter(created_at__gte=start_dt, created_at__lt=end_dt).count()
    claims_prev = WarrantyClaim.objects.filter(
        created_at__gte=start_prev, created_at__lt=start_dt
    ).count()
    claims_delta_pct = 0
    if claims_prev:
        claims_delta_pct = round((claims_this - claims_prev) / claims_prev * 100)
    elif claims_this:
        claims_delta_pct = 100

    # Tasa de reclamos (% de líneas vendidas que generaron reclamo este mes)
    claims_rate_pct = (claims_this / items_sold_count * 100) if items_sold_count else Decimal("0")

    # Costo promedio por reclamo (referencial, últimos 12 meses)
    from django.db.models import Avg
    year_ago = now - timedelta(days=365)
    claim_avg = WarrantyClaim.objects.filter(
        created_at__gte=year_ago
    ).aggregate(avg=Avg("order_item__cost_price_snapshot"))
    avg_claim_cost = (claim_avg.get("avg") or Decimal("0")) or Decimal("150000")

    # Distribución de días de garantía en ventas recientes (últimos 90 días)
    cutoff = now - timedelta(days=90)
    warranty_days_used = list(
        OrderItem.objects.filter(
            order__created_at__gte=cutoff,
            order__status__in=REAL_SALES_STATUSES,
            warranty_days_applied__isnull=False,
        )
        .values_list("warranty_days_applied", flat=True)
    )
    most_common_days = Counter(warranty_days_used).most_common(3) if warranty_days_used else []

    config = ConfiguracionEmpresa.get_singleton()
    current_days = config.warranty_days
    margen_min = float(config.margen_minimo_recomendado or 15)

    # Líneas vendidas bajo margen mínimo (margen línea < margen_min%)
    margin_below_min_count = 0
    for item in items_month.only(
        "unit_price_applied", "quantity", "discount_amount_applied", "cost_price_snapshot"
    )[:500]:
        line_rev = item.unit_price_applied * item.quantity - item.discount_amount_applied
        line_cost = item.cost_price_snapshot * item.quantity
        if line_rev <= 0:
            continue
        line_margin_pct = (line_rev - line_cost) / line_rev * 100
        if line_margin_pct < margen_min:
            margin_below_min_count += 1

    # Indicador de exposición y riesgo financiero % (0-100) para cockpit
    exposicion, exposicion_label = _exposure_for_days(current_days)[:2]
    risk_financiero_pct = _exposure_for_days(current_days)[2]

    # Impacto estimado mensual por garantía (heurística: más días → más reclamos potenciales)
    # Referencial: claims_this * avg_claim_cost; si subes días, proyectamos +X% reclamos
    base_impact = float(claims_this * avg_claim_cost)
    if current_days <= 10:
        impact_estimate_monthly = int(base_impact * 0.8)
    elif current_days <= 30:
        impact_estimate_monthly = int(base_impact * 1.0)
    else:
        impact_estimate_monthly = int(base_impact * (1 + (current_days - 30) / 60))

    # Simulaciones: 10, 30, 90 días
    scenario_days = [10, 30, 90]
    scenario_simulations = []
    for d in scenario_days:
        ex, ex_label, risk = _exposure_for_days(d)
        factor = 0.5 + (d / 90) * 0.5
        est = int(base_impact * factor * (1 + (d - current_days) / 90 * 0.15))
        est = max(0, est)
        scenario_simulations.append({
            "days": d,
            "exposure": ex,
            "exposure_label": ex_label,
            "risk_pct": risk,
            "impact_estimate_clp": est,
            "impact_display": f"{est:,}".replace(",", "."),
        })

    # Frase asesor (personalidad dueño)
    if margen_pct >= margen_min + 5:
        advisor_message = (
            f"Tu margen actual promedio es {margen_pct:.1f}%. "
            "Estás en rango saludable. Sigue monitoreando."
        )
        advisor_message_class = "success"
    elif margen_pct >= margen_min:
        advisor_message = (
            f"Tu margen actual promedio es {margen_pct:.1f}%. "
            f"Estás en el límite del mínimo recomendado ({margen_min:.0f}%). "
            "Revisa precios o descuentos para mejorar rentabilidad."
        )
        advisor_message_class = "warning"
    else:
        advisor_message = (
            f"Tu margen actual promedio es {margen_pct:.1f}%. "
            f"Estás bajo el nivel recomendado ({margen_min:.0f}%). "
            "Podrías estar perdiendo rentabilidad sin darte cuenta."
        )
        advisor_message_class = "danger"

    recommendations = []
    if most_common_days and most_common_days[0][0] != current_days:
        d = most_common_days[0][0]
        recommendations.append({
            "type": "warning",
            "text": f"La mayoría de tus ventas recientes usan garantía de {d} días. Considera alinear la garantía por defecto a {d} días.",
        })
    if claims_delta_pct > 5 and claims_this > 0:
        recommendations.append({
            "type": "warning",
            "text": f"Tus reclamos de garantía aumentaron {claims_delta_pct}% este mes respecto al anterior.",
        })
    if not recommendations:
        recommendations.append({
            "type": "info",
            "text": "Puedes ofrecer garantía extendida pagada como opción en ventas.",
        })

    # Alertas estratégicas (predictivas)
    strategic_alerts = []
    if margin_mom_delta_pct < -2 and float(margen_pct) < margen_min:
        strategic_alerts.append({
            "level": "danger",
            "message": f"Tu margen promedio cayó {abs(margin_mom_delta_pct)}% este mes y está bajo el mínimo recomendado.",
        })
    elif margin_mom_delta_pct < -2:
        strategic_alerts.append({
            "level": "warning",
            "message": f"Tu margen promedio cayó {abs(margin_mom_delta_pct)}% este mes.",
        })
    if margin_below_min_count > 0:
        strategic_alerts.append({
            "level": "danger" if margin_below_min_count >= 3 else "warning",
            "message": f"Has vendido {margin_below_min_count} línea(s) bajo margen mínimo recomendado ({margen_min:.0f}%).",
        })
    if claims_this > 0 and float(claims_rate_pct) > 5:
        strategic_alerts.append({
            "level": "warning",
            "message": f"Tasa de reclamos este mes: {claims_rate_pct:.1f}% de las ventas. Revisa calidad o política de garantía.",
        })

    return {
        "margen_pct": round(margen_pct, 1),
        "margen_prev_pct": round(margen_prev, 1),
        "margin_mom_delta_pct": margin_mom_delta_pct,
        "claims_this_month": claims_this,
        "claims_prev_month": claims_prev,
        "claims_delta_pct": claims_delta_pct,
        "claims_rate_pct": round(float(claims_rate_pct), 1),
        "items_sold_this_month": items_sold_count,
        "recommendations": recommendations,
        "exposicion": exposicion,
        "exposicion_label": exposicion_label,
        "risk_financiero_pct": risk_financiero_pct,
        "most_common_warranty_days": most_common_days[0][0] if most_common_days else current_days,
        "advisor_message": advisor_message,
        "advisor_message_class": advisor_message_class,
        "margen_minimo_recomendado": margen_min,
        "margin_below_min_count": margin_below_min_count,
        "impact_estimate_monthly": impact_estimate_monthly,
        "scenario_simulations": scenario_simulations,
        "strategic_alerts": strategic_alerts,
        "avg_claim_cost": avg_claim_cost,
        "impact_estimate_monthly_display": f"{int(impact_estimate_monthly):,}".replace(",", "."),
    }


@owner_only
@require_http_methods(["GET", "POST"])
def settings_view(request):
    from apps.ops.models import ConfiguracionEmpresa
    config = ConfiguracionEmpresa.get_singleton()

    if request.method == "POST":
        # Guardar bloque garantía
        days_raw = request.POST.get("warranty_days")
        if days_raw is not None:
            try:
                config.warranty_days = max(1, min(365, int(days_raw)))
            except (ValueError, TypeError):
                pass
        terms = request.POST.get("warranty_terms")
        if terms is not None:
            config.warranty_terms = terms
        # Guardar toggles estratégicos
        for field in (
            "alertas_margen_bajo", "modo_estricto_precios", "alerta_stock_critico",
            "bloqueo_venta_sin_stock", "notif_whatsapp", "notif_email",
            "aviso_ventas_altas", "aviso_perdidas",
        ):
            if request.POST.get(field) == "on" or request.POST.get(field) == "1":
                setattr(config, field, True)
            else:
                setattr(config, field, False)
        dias_inventario = request.POST.get("dias_max_inventario")
        if dias_inventario is not None and dias_inventario.strip() != "":
            try:
                config.dias_max_inventario = max(1, int(dias_inventario))
            except (ValueError, TypeError):
                config.dias_max_inventario = None
        else:
            config.dias_max_inventario = None
        for field, default in (("comision_vendedores_pct", "0"), ("margen_minimo_recomendado", "15")):
            val = request.POST.get(field, default)
            try:
                setattr(config, field, Decimal(str(val).replace(",", ".")))
            except (ValueError, TypeError, Exception):
                pass
        config.save()
        messages.success(request, "Configuración guardada correctamente.")
        return redirect("ops:settings")

    data = _settings_metrics_and_recommendations()
    data["config"] = config
    data["default_warranty_days"] = config.warranty_days
    data["default_warranty_terms"] = config.warranty_terms

    # Estado del sistema (resumen)
    margen = data["margen_pct"]
    if margen >= 25 and data["exposicion"] != "high":
        data["sistema_estado"] = "Óptimo"
        data["sistema_estado_class"] = "success"
    elif margen >= 10 or data["exposicion"] == "low":
        data["sistema_estado"] = "Atención"
        data["sistema_estado_class"] = "warning"
    else:
        data["sistema_estado"] = "Revisar"
        data["sistema_estado_class"] = "danger"

    return render(request, "ops/settings.html", data)


# --- Catálogo (Admin) ---

def _catalog_admin_can_access(user):
    """Usuario puede administrar catálogo si es staff o tiene permiso catalog.change_product."""
    return user.is_authenticated and (user.is_staff or user.has_perm("catalog.change_product"))


@catalog_admin_required
@require_http_methods(["GET", "POST"])
def catalog_admin_add(request):
    """Crear nuevo producto. GET ?cat=slug o ?category=id preselecciona la categoría."""
    initial = {}
    cat_slug = request.GET.get("cat", "").strip()
    cat_id = request.GET.get("category", "").strip()
    if cat_slug:
        try:
            cat = Category.objects.get(slug=cat_slug, is_active=True)
            initial["category"] = cat.pk
        except Category.DoesNotExist:
            pass
    elif cat_id:
        try:
            cat = Category.objects.get(pk=int(cat_id), is_active=True)
            initial["category"] = cat.pk
        except (Category.DoesNotExist, ValueError):
            pass

    initial_category = None
    if initial.get("category"):
        try:
            initial_category = Category.objects.get(pk=initial["category"])
        except Category.DoesNotExist:
            pass

    form = ProductAdminForm(initial=initial)
    formset = ProductImageFormSet(instance=Product())

    if request.method == "POST":
        form = ProductAdminForm(request.POST)
        if form.is_valid():
            product = form.save()
            formset = ProductImageFormSet(
                request.POST, request.FILES, instance=product
            )
            if formset.is_valid():
                formset.save()
            product.refresh_quality(save=True)
            messages.success(request, f"Producto «{product.name}» creado correctamente.")
            return redirect("ops:catalog_admin_detail", slug=product.slug)
        formset = ProductImageFormSet(request.POST, request.FILES, instance=Product())
        messages.error(request, "Corrige los errores del formulario.")

    return render(
        request,
        "ops/catalog_admin_add.html",
        {"form": form, "formset": formset, "initial_category": initial_category},
    )


@catalog_admin_required
@require_http_methods(["GET"])
def catalog_admin_cataliticos_choice(request):
    """Página de opciones: Euro 3, Euro 4, Euro 5, Diesel, Ensamble Directo CLF (una sola tarjeta)."""
    from apps.catalog.views import CLF_ENSAMBLE_SLUGS

    subcat_slugs = (
        "cataliticos-twc-euro3",
        "cataliticos-twc-euro4",
        "cataliticos-twc-euro5",
        "cataliticos-twc-diesel",
        "cataliticos-ensamble-directo",
    )
    subcategories = list(
        Category.objects.filter(slug__in=subcat_slugs, is_active=True)
    )
    order = {s: i for i, s in enumerate(subcat_slugs)}
    subcategories.sort(key=lambda c: order.get(c.slug, 99))

    # Imágenes de productos por categoría para el “video” en cada tarjeta (máx 14 por categoría)
    euro_categories_with_previews = []
    for cat in subcategories:
        if cat.slug == "cataliticos-ensamble-directo":
            products = list(
                Product.objects.filter(category__slug__in=CLF_ENSAMBLE_SLUGS, is_active=True)
                .prefetch_related("images")[:14]
            )
        else:
            products = list(
                Product.objects.filter(category=cat, is_active=True)
                .prefetch_related("images")[:14]
            )
        urls = []
        for p in products:
            img = p.images.order_by("position").first()
            if img and img.image:
                urls.append(img.image.url)
        euro_categories_with_previews.append({"category": cat, "preview_urls": urls})

    return render(
        request,
        "ops/catalog_admin_cataliticos_choice.html",
        {"euro_categories_with_previews": euro_categories_with_previews},
    )


@catalog_admin_required
@require_http_methods(["GET"])
def catalog_admin_list(request):
    """Listado tipo catálogo: mismo aspecto y orden que catálogo público, con botones Ver/Editar/Borrar."""
    q = request.GET.get("q", "").strip()
    cat_slug = request.GET.get("cat", "").strip()
    sort_param = (request.GET.get("sort") or "").strip().lower()
    if sort_param not in ("name", "price", "price_desc"):
        sort_param = ""
    # Unificar flexibles: flexibles-reforzados → flexibles
    if cat_slug == "flexibles-reforzados":
        get_copy = request.GET.copy()
        get_copy["cat"] = "flexibles"
        return redirect("ops:catalog_admin_list" + "?" + get_copy.urlencode())
    try:
        page_size = int(request.GET.get("page_size", 24))
    except (TypeError, ValueError):
        page_size = 24
    page_size = min(max(page_size, 12), 48)
    page_number = request.GET.get("page", 1)

    # Categorías raíz para el sidebar (idéntico al catálogo público)
    root_categories = (
        Category.objects.filter(is_active=True, parent__isnull=True)
        .prefetch_related("children")
        .order_by("name")
    )
    root_categories = list(root_categories)
    root_categories = [r for r in root_categories if r.slug != "flexibles-reforzados"]
    SILENCIADORES_SLUGS = {"silenciadores", "silenciadores-alto-flujo", "silenciadores-de-alto-flujo"}
    slugs_present = {r.slug for r in root_categories}
    if len(slugs_present & SILENCIADORES_SLUGS) > 1:
        root_categories = [
            r for r in root_categories
            if r.slug not in ("silenciadores", "silenciadores-de-alto-flujo")
        ]
    if not root_categories:
        root_categories = list(
            Category.objects.filter(is_active=True)
            .annotate(num_products=Count("products"))
            .filter(num_products__gt=0)
            .order_by("name")
        )
        for r in root_categories:
            r.children_list = getattr(r, "children_list", [])
    else:
        CATALITICOS_CHILD_ORDER = ("cataliticos-twc", "cataliticos-clf", "cataliticos-ensamble-directo")
        EURO_TWC_SLUG_ORDER = ("cataliticos-twc-euro3", "cataliticos-twc-euro4", "cataliticos-twc-euro5", "cataliticos-twc-diesel")
        for r in root_categories:
            children = [c for c in r.children.all() if c.is_active]
            if r.slug == "cataliticos" and children:
                children.sort(key=lambda c: (CATALITICOS_CHILD_ORDER.index(c.slug) if c.slug in CATALITICOS_CHILD_ORDER else 99, c.slug))
            elif r.slug == "cataliticos-twc" and children:
                children.sort(key=lambda c: (EURO_TWC_SLUG_ORDER.index(c.slug) if c.slug in EURO_TWC_SLUG_ORDER else 99, c.slug))
            r.children_list = children

    # Productos: mismo orden que catálogo público (Resonadores, Silenciadores, resto; flexibles por medida; Euro 5 TWCAT052-16 primero)
    CAT_ORDER = [
        ("resonadores", 0),
        ("silenciadores-alto-flujo", 1),
        ("silenciadores-de-alto-flujo", 2),
        ("silenciadores", 3),
    ]
    category_order_cases = [When(category__slug=slug, then=order) for slug, order in CAT_ORDER]
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
    products_qs = _apply_category_filter(products_qs, cat_slug)
    products_qs = _smart_search_queryset(products_qs, q)
    cataliticos_subcat_slugs = (
        "cataliticos-twc", "cataliticos-twc-euro3", "cataliticos-twc-euro4",
        "cataliticos-twc-euro5", "cataliticos-twc-diesel",
        "cataliticos-clf", "cataliticos-ensamble-directo",
    )
    if cat_slug in cataliticos_subcat_slugs:
        products_qs = products_qs.prefetch_related("compatibilities__model__brand")
    product_list = order_products_for_display(list(products_qs), cat_slug, sort_param)
    paginator = Paginator(product_list, page_size)
    page = paginator.get_page(page_number)

    current_category = None
    if cat_slug:
        try:
            current_category = Category.objects.get(slug=cat_slug, is_active=True)
        except Category.DoesNotExist:
            if cat_slug in ("silenciadores", "silenciadores-de-alto-flujo"):
                current_category = Category.objects.filter(
                    slug="silenciadores-alto-flujo", is_active=True
                ).first()

    is_cataliticos_subcat = cat_slug in cataliticos_subcat_slugs and bool(page.object_list or q)

    return render(
        request,
        "ops/catalog_admin_list.html",
        {
            "page": page,
            "products": page.object_list,
            "q": q,
            "root_categories": root_categories,
            "current_category": current_category,
            "cat_slug": cat_slug,
            "sort_param": sort_param,
            "is_cataliticos_subcat": is_cataliticos_subcat,
        },
    )


@catalog_admin_required
@require_http_methods(["GET"])
def catalog_admin_detail(request, slug):
    """Detalle del producto en modo admin (incluye inactivos)."""
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images", "compatibilities"),
        slug=slug,
        deleted_at__isnull=True,
    )
    return render(request, "ops/catalog_admin_detail.html", {"product": product})


@catalog_admin_required
@require_http_methods(["GET"])
def catalog_admin_detail_by_pk(request, pk):
    """Detalle admin tolerante a productos legacy sin slug."""
    product = get_object_or_404(
        Product.objects.select_related("category").prefetch_related("images", "compatibilities"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if product.slug:
        return redirect("ops:catalog_admin_detail", slug=product.slug)
    return render(request, "ops/catalog_admin_detail.html", {"product": product})


@catalog_admin_required
@require_http_methods(["GET", "POST"])
def catalog_admin_edit(request, slug):
    """Editar producto (form + formset imágenes)."""
    product = get_object_or_404(
        Product.objects.prefetch_related("images"),
        slug=slug,
        deleted_at__isnull=True,
    )
    form = ProductAdminForm(instance=product)
    formset = ProductImageFormSet(instance=product)

    if request.method == "POST":
        form = ProductAdminForm(request.POST, instance=product)
        formset = ProductImageFormSet(
            request.POST, request.FILES, instance=product
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            product.refresh_quality(save=True)
            messages.success(request, f"Producto «{product.name}» actualizado correctamente.")
            return redirect("ops:catalog_admin_detail", slug=product.slug)
        messages.error(request, "Corrige los errores del formulario.")

    return render(
        request,
        "ops/catalog_admin_edit.html",
        {"product": product, "form": form, "formset": formset},
    )


@catalog_admin_required
@require_http_methods(["GET", "POST"])
def catalog_admin_edit_by_pk(request, pk):
    """Editar producto por PK para registros legacy sin slug."""
    product = get_object_or_404(
        Product.objects.prefetch_related("images"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if request.method == "GET" and product.slug:
        return redirect("ops:catalog_admin_edit", slug=product.slug)

    form = ProductAdminForm(instance=product)
    formset = ProductImageFormSet(instance=product)

    if request.method == "POST":
        form = ProductAdminForm(request.POST, instance=product)
        formset = ProductImageFormSet(
            request.POST, request.FILES, instance=product
        )
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            product.refresh_quality(save=True)
            messages.success(request, f"Producto «{product.name}» actualizado correctamente.")
            return redirect(product.get_ops_admin_detail_url())
        messages.error(request, "Corrige los errores del formulario.")

    return render(
        request,
        "ops/catalog_admin_edit.html",
        {"product": product, "form": form, "formset": formset},
    )


@catalog_admin_required
@require_http_methods(["GET", "POST"])
def catalog_admin_delete(request, slug):
    """Eliminar producto (soft delete). Solo POST para confirmar."""
    product = get_object_or_404(
        Product.objects.select_related("category"),
        slug=slug,
        deleted_at__isnull=True,
    )
    if request.method == "POST":
        name = product.name
        product.soft_delete()
        messages.success(request, f"Producto «{name}» ha sido eliminado (desactivado).")
        return redirect("ops:catalog_admin_list")
    return render(request, "ops/catalog_admin_confirm_delete.html", {"product": product})


@catalog_admin_required
@require_http_methods(["GET", "POST"])
def catalog_admin_delete_by_pk(request, pk):
    """Eliminar producto por PK para registros legacy sin slug."""
    product = get_object_or_404(
        Product.objects.select_related("category"),
        pk=pk,
        deleted_at__isnull=True,
    )
    if request.method == "GET" and product.slug:
        return redirect("ops:catalog_admin_delete", slug=product.slug)

    if request.method == "POST":
        name = product.name
        product.soft_delete()
        messages.success(request, f"Producto «{name}» ha sido eliminado (desactivado).")
        return redirect("ops:catalog_admin_list")
    return render(request, "ops/catalog_admin_confirm_delete.html", {"product": product})
