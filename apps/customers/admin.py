from django.contrib import admin
from .models import CustomerProfile


@admin.register(CustomerProfile)
class CustomerProfileAdmin(admin.ModelAdmin):
    list_display = ("id", "customer_type", "discount_percent", "is_internal_active", "company_name", "rut", "user")
    list_filter = ("customer_type", "is_internal_active")
    search_fields = ("company_name", "rut", "user__username", "user__email")
