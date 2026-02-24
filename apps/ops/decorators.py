from functools import wraps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.contrib import messages


def ops_required(view_func):
    """
    Acceso solo para usuarios en grupo OWNER o ADMIN_OPERACIONES.
    """
    @wraps(view_func)
    @login_required(login_url="/admin/login/")
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/admin/login/?next=" + request.get_full_path())
        owner = getattr(settings, "OPS_GROUP_OWNER", "OWNER")
        admin_ops = getattr(settings, "OPS_GROUP_ADMIN_OPERACIONES", "ADMIN_OPERACIONES")
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        if request.user.groups.filter(name__in=[owner, admin_ops]).exists():
            return view_func(request, *args, **kwargs)
        messages.error(request, "No tienes permiso para acceder al Centro de Operaciones.")
        return redirect("/admin/")
    return _wrapped


def owner_only(view_func):
    """Solo OWNER (o superuser). Para configuración sensible."""
    @wraps(view_func)
    @login_required(login_url="/admin/login/")
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/admin/login/?next=" + request.get_full_path())
        owner = getattr(settings, "OPS_GROUP_OWNER", "OWNER")
        if request.user.is_superuser or request.user.groups.filter(name=owner).exists():
            return view_func(request, *args, **kwargs)
        messages.error(request, "Solo el dueño puede acceder a esta sección.")
        return redirect("ops:dashboard")
    return _wrapped


def catalog_admin_required(view_func):
    """
    Acceso solo para usuarios con is_staff o permiso catalog.change_product.
    Para listado/edición/borrado de productos en Centro de Operaciones.
    """
    @wraps(view_func)
    @login_required(login_url="/admin/login/")
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("/admin/login/?next=" + request.get_full_path())
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        if request.user.has_perm("catalog.change_product"):
            return view_func(request, *args, **kwargs)
        messages.error(request, "No tienes permiso para administrar el catálogo.")
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden(
            "<h1>403 Forbidden</h1><p>No tienes permiso para acceder a esta sección.</p>"
        )
    return _wrapped
