from django.shortcuts import get_object_or_404, render
from .models import Post, BlogCategory


def post_list(request):
    posts = Post.objects.filter(is_published=True).select_related("author", "category").order_by("-published_at", "-created_at")[:50]
    return render(request, "blog/blog_list.html", {"posts": posts})


def post_detail(request, slug):
    post = get_object_or_404(Post.objects.select_related("author", "category"), slug=slug, is_published=True)
    return render(request, "blog/blog_detail.html", {"post": post})


def category_list(request, slug):
    category = get_object_or_404(BlogCategory, slug=slug)
    posts = Post.objects.filter(category=category, is_published=True).select_related("author").order_by("-published_at")
    return render(request, "blog/blog_category.html", {"category": category, "posts": posts})
