"""
Sitemaps para SEO: /sitemap.xml

Django sirve un índice que enlaza a cada sección:
- sitemap.xml?section=static   → páginas fijas (home, listados, normativas, blog, páginas legales)
- sitemap.xml?section=categories → filtros por categoría (?cat=slug)
- sitemap.xml?section=products → detalle de cada producto (slug)
- sitemap.xml?section=blog     → entradas publicadas del blog
- sitemap.xml?section=vehicles → landings por vehículo (marca/modelo/año) indexables para SEO

Todas las secciones usan protocol = "https" para que las URLs del XML sean HTTPS (recomendado por Sitemaps Protocol y Search Console).
"""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from apps.catalog.models import Product, Category, ProductCompatibility
from apps.catalog.public_visibility import (
    exclude_removed_categories,
    exclude_removed_products,
    removed_product_q,
)


class StaticViewSitemap(Sitemap):
    """Páginas fijas: home, buscador, listado productos, normativas, blog, nosotros, garantías, etc."""
    protocol = "https"
    changefreq = "weekly"
    priority = 0.8

    def items(self):
        return [
            "core:home",
            "core:vehicle_search",
            "catalog:product_list",
            "normativas",
            "blog:list",
            "nosotros",
            "garantias",
            "devoluciones",
            "faq",
        ]

    def location(self, item):
        return reverse(item)


class CategorySitemap(Sitemap):
    """URLs de filtro por categoría: /productos/?cat=<slug>."""
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        return exclude_removed_categories(Category.objects.filter(is_active=True)).order_by("slug")

    def location(self, obj):
        return reverse("catalog:product_list") + f"?cat={obj.slug}"


class ProductSitemap(Sitemap):
    """Detalle de cada producto: /productos/<slug>/."""
    protocol = "https"
    changefreq = "daily"  # Stock/precios pueden cambiar a diario (management commands).
    priority = 0.9

    def items(self):
        return exclude_removed_products(
            Product.objects.filter(
                is_active=True, deleted_at__isnull=True
            )
        ).order_by("id")

    def lastmod(self, obj):
        return obj.updated_at or obj.created_at

    def location(self, obj):
        return obj.get_absolute_url()


class BlogPostSitemap(Sitemap):
    """Entradas del blog publicadas."""
    protocol = "https"
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        try:
            from apps.blog.models import Post
            return Post.objects.filter(is_published=True).order_by("-published_at", "id")
        except Exception:
            return []

    def lastmod(self, obj):
        return obj.updated_at or obj.published_at

    def location(self, obj):
        return obj.get_absolute_url()


class VehicleLandingSitemap(Sitemap):
    """
    Landings por vehículo: /buscar-por-vehiculo/?brand=X&model=Y&year=Z
    Una URL por cada (brand_id, model_id, year) que tiene al menos un producto compatible.
    """
    protocol = "https"
    changefreq = "weekly"
    priority = 0.7

    def items(self):
        # Combinaciones (brand_id, model_id, year) con productos publicables; orden fijo para paginación consistente
        qs = (
            ProductCompatibility.objects.filter(
                is_active=True,
                product__is_publishable=True,
                product__is_active=True,
                product__deleted_at__isnull=True,
            )
            .exclude(removed_product_q("product__"))
            .order_by("brand_id", "model_id", "year_from")
            .values_list("brand_id", "model_id", "year_from")
            .distinct()
        )
        return list(qs)

    def location(self, item):
        brand_id, model_id, year = item
        return reverse("core:vehicle_search") + f"?brand={brand_id}&model={model_id}&year={year}"
