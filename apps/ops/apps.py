from django.apps import AppConfig


def ensure_ops_groups(*args, **kwargs):
    """Crea los grupos de ops si no existen. Ejecutar en post_migrate, no en ready()."""
    from django.conf import settings
    from django.contrib.auth.models import Group
    for name in (
        getattr(settings, "OPS_GROUP_OWNER", "OWNER"),
        getattr(settings, "OPS_GROUP_ADMIN_OPERACIONES", "ADMIN_OPERACIONES"),
        getattr(settings, "OPS_GROUP_CATALOGO", "CATALOGO"),
    ):
        Group.objects.get_or_create(name=name)


class OpsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.ops"
    verbose_name = "Centro de Operaciones"

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(ensure_ops_groups, sender=self)
