from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ["product", "user", "rating", "is_approved", "created_at"]
    list_filter = ["is_approved", "rating"]
    search_fields = ["product__sku", "product__name", "user__email", "body"]
    raw_id_fields = ["product", "user", "order"]
    readonly_fields = ["created_at"]
