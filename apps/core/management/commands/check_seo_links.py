"""
Auditoría de enlaces SEO: verifica que las URLs principales y de catálogo devuelvan 200.
Google penaliza 404s durante la indexación. Ejecutar antes de despliegues o semanalmente.

Uso:
    python manage.py check_seo_links
    python manage.py check_seo_links --products 50
    python manage.py check_seo_links --categories
    python manage.py check_seo_links --vehicles 10

En PythonAnywhere/servidor: asegúrate de que ALLOWED_HOSTS incluya localhost o 127.0.0.1.
Si no, define CHECK_SEO_LINKS_HOST en settings (ej. monteazulspa.cl) para las peticiones.
"""
from django.core.management.base import BaseCommand
from django.urls import reverse
from django.test import Client
from django.conf import settings

# Host permitido para las peticiones (evita DisallowedHost con testserver)
DEFAULT_HOST = "localhost"


class Command(BaseCommand):
    help = "Verifica que las URLs principales y de productos funcionen (Status 200). Evita 404 que Google penaliza."

    def add_arguments(self, parser):
        parser.add_argument(
            "--products",
            type=int,
            default=20,
            help="Número de productos a probar (0 = todos). Por defecto 20.",
        )
        parser.add_argument(
            "--categories",
            action="store_true",
            help="Incluir URLs de categorías (/productos/?cat=slug).",
        )
        parser.add_argument(
            "--vehicles",
            type=int,
            default=0,
            metavar="N",
            help="Probar hasta N landings de vehículo (0 = no probar).",
        )

    def handle(self, *args, **options):
        self.client = Client()
        self.extra = {"HTTP_HOST": getattr(settings, "CHECK_SEO_LINKS_HOST", DEFAULT_HOST)}
        self.errors = 0
        self.redirects = 0
        self.ok = 0

        self.stdout.write(self.style.SUCCESS("--- Auditoría de enlaces SEO ---\n"))

        # 1. URLs estáticas / páginas principales
        url_names = [
            ("core:home", "Home"),
            ("core:vehicle_search", "Buscar por vehículo"),
            ("catalog:product_list", "Listado productos"),
            ("normativas", "Normativas"),
            ("blog:list", "Blog"),
            ("nosotros", "Nosotros"),
            ("garantias", "Garantías"),
            ("devoluciones", "Devoluciones"),
            ("faq", "FAQ"),
        ]
        self.stdout.write(self.style.HTTP_INFO("[1] Páginas principales"))
        for name, label in url_names:
            try:
                url = reverse(name)
            except Exception as e:
                self._report(url=name, code=None, error=str(e))
                continue
            resp = self.client.get(url, **self.extra)
            self._report(url, resp.status_code)

        # 2. Sitemap y robots
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO("[2] SEO (sitemap, robots)"))
        for path in ["/sitemap.xml", "/robots.txt"]:
            resp = self.client.get(path, **self.extra)
            self._report(path, resp.status_code)

        # 3. Productos (slugs)
        from apps.catalog.models import Product
        from apps.catalog.public_visibility import exclude_removed_categories, exclude_removed_products

        qs = exclude_removed_products(Product.objects.filter(is_active=True, deleted_at__isnull=True))
        limit = options["products"]
        if limit > 0:
            qs = qs[:limit]
        total = qs.count()
        self.stdout.write("")
        self.stdout.write(self.style.HTTP_INFO(f"[3] Productos (hasta {total})"))
        for prod in qs:
            url = prod.get_absolute_url()
            resp = self.client.get(url, **self.extra)
            self._report(url, resp.status_code)

        # 4. Categorías (opcional)
        if options["categories"]:
            from apps.catalog.models import Category

            self.stdout.write("")
            self.stdout.write(self.style.HTTP_INFO("[4] Categorías (/productos/?cat=slug)"))
            for cat in exclude_removed_categories(Category.objects.filter(is_active=True))[:30]:
                url = reverse("catalog:product_list") + f"?cat={cat.slug}"
                resp = self.client.get(url, **self.extra)
                self._report(url, resp.status_code)

        # 5. Landings de vehículo (opcional)
        if options["vehicles"] > 0:
            from apps.catalog.models import ProductCompatibility

            self.stdout.write("")
            self.stdout.write(self.style.HTTP_INFO(f"[5] Landings vehículo (hasta {options['vehicles']})"))
            qs = (
                ProductCompatibility.objects.filter(
                    is_active=True,
                    product__is_publishable=True,
                    product__is_active=True,
                    product__deleted_at__isnull=True,
                )
                .values_list("brand_id", "model_id", "year_from")
                .distinct()[: options["vehicles"]]
            )
            for brand_id, model_id, year in qs:
                url = reverse("core:vehicle_search") + f"?brand={brand_id}&model={model_id}&year={year}"
                resp = self.client.get(url, **self.extra)
                self._report(url, resp.status_code)

        # Resumen
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"--- Resumen: OK={self.ok} | Redirects={self.redirects} | Errores={self.errors} ---"))
        if self.errors:
            self.stdout.write(self.style.ERROR("Corrige los errores antes de confiar en la indexación."))

    def _report(self, url, code, error=None):
        if error:
            self.stdout.write(self.style.ERROR(f"ERROR: {url} -> {error}"))
            self.errors += 1
            return
        if code == 200:
            self.stdout.write(f"  OK [200]: {url}")
            self.ok += 1
        elif code in (301, 302):
            self.stdout.write(self.style.WARNING(f"  REDIRECT [{code}]: {url}"))
            self.redirects += 1
        else:
            self.stdout.write(self.style.ERROR(f"  ERROR [{code}]: {url}"))
            self.errors += 1
