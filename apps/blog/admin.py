from django.contrib import admin
from .models import BlogCategory, Post


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "is_published", "published_at", "author", "created_at"]
    list_filter = ["is_published", "category"]
    search_fields = ["title", "excerpt", "content"]
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ["author", "category"]
    date_hierarchy = "published_at"
