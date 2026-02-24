from django.urls import path
from . import views

app_name = "ops"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("seo/", views.seo_dashboard, name="seo_dashboard"),
    path("sales/", views.sales_list, name="sales_list"),
    path("sales/<int:pk>/", views.sales_detail, name="sales_detail"),
    path("sales/<int:pk>/cancel/", views.sales_cancel, name="sales_cancel"),
    path("inventory/", views.inventory_list, name="inventory_list"),
    path("inventory/movements/", views.inventory_movements, name="inventory_movements"),
    path("inventory/movements/<int:product_id>/", views.inventory_movements, name="inventory_movements_product"),
    path("customers/", views.customers_list, name="customers_list"),
    path("customers/<int:pk>/", views.customers_detail, name="customers_detail"),
    path("warranties/", views.warranties_list, name="warranties_list"),
    path("warranties/<int:pk>/", views.warranties_detail, name="warranties_detail"),
    path("reports/", views.reports_index, name="reports_index"),
    path("reports/sales/", views.reports_sales, name="reports_sales"),
    path("settings/", views.settings_view, name="settings"),
    # Catálogo (Admin) - solo staff o permiso catalog.change_product
    path("catalogo/", views.catalog_admin_list, name="catalog_admin_list"),
    path("catalogo/agregar/", views.catalog_admin_add, name="catalog_admin_add"),
    path("catalogo/convertidores-cataliticos/", views.catalog_admin_cataliticos_choice, name="catalog_admin_cataliticos_choice"),
    path("catalogo/<slug:slug>/", views.catalog_admin_detail, name="catalog_admin_detail"),
    path("catalogo/<slug:slug>/editar/", views.catalog_admin_edit, name="catalog_admin_edit"),
    path("catalogo/<slug:slug>/eliminar/", views.catalog_admin_delete, name="catalog_admin_delete"),
]
