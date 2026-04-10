from django import template

from apps.catalog.utils import get_product_image_url

register = template.Library()


@register.filter
def get_image(product):
    return get_product_image_url(product)
