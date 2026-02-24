from django.contrib import admin
from .models import ConfiguracionEmpresa


@admin.register(ConfiguracionEmpresa)
class ConfiguracionEmpresaAdmin(admin.ModelAdmin):
    list_display = ["id", "warranty_days", "actualizado"]
    readonly_fields = ["actualizado"]

    def has_add_permission(self, request):
        # Solo una instancia (singleton)
        return not ConfiguracionEmpresa.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
