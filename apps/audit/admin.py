from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "model", "object_id", "user", "timestamp")
    list_filter = ("action",)
    readonly_fields = ("user", "action", "model", "object_id", "description", "timestamp")
