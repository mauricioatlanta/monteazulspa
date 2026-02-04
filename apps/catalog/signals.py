from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Product, ProductImage, ProductCompatibility


@receiver(post_save, sender=ProductImage)
def product_image_post_save(sender, instance: ProductImage, created, **kwargs):
    instance.product.refresh_quality(save=True)


@receiver(post_save, sender=ProductCompatibility)
def product_compat_post_save(sender, instance: ProductCompatibility, created, **kwargs):
    instance.product.refresh_quality(save=True)
