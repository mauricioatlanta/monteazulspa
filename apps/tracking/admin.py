from django.contrib import admin
from .models import TrackingEvent


@admin.register(TrackingEvent)
class TrackingEventAdmin(admin.ModelAdmin):
    list_display = ['event', 'created_at', 'ip_address', 'payload_preview']
    list_filter = ['event', 'created_at']
    search_fields = ['event', 'ip_address', 'payload']
    readonly_fields = ['created_at', 'ip_address', 'user_agent']
    date_hierarchy = 'created_at'
    
    def payload_preview(self, obj):
        """Muestra preview del payload en el listado"""
        import json
        payload_str = json.dumps(obj.payload, ensure_ascii=False)
        if len(payload_str) > 100:
            return payload_str[:100] + '...'
        return payload_str
    payload_preview.short_description = 'Payload'
    
    def has_add_permission(self, request):
        """No permitir agregar eventos manualmente desde admin"""
        return False
