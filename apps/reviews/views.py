from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from apps.catalog.models import Product
from .models import Review
from .forms import ReviewForm
from .services import user_can_review


@login_required
def review_submit(request, slug):
    """Enviar reseña. Solo si el usuario compró el producto."""
    product = get_object_or_404(Product, slug=slug, is_active=True, deleted_at__isnull=True)
    if not user_can_review(request.user, product):
        messages.error(request, "Solo los clientes que compraron este producto pueden dejar una reseña.")
        return redirect("catalog:product_detail", slug=slug)

    if request.method != "POST":
        return redirect("catalog:product_detail", slug=slug)

    form = ReviewForm(request.POST)
    if form.is_valid():
        review, created = Review.objects.update_or_create(
            product=product,
            user=request.user,
            defaults={
                "rating": form.cleaned_data["rating"],
                "title": form.cleaned_data.get("title", ""),
                "body": form.cleaned_data["body"],
                "is_approved": False,
            },
        )
        msg = "Tu reseña fue guardada y está pendiente de moderación." if created else "Tu reseña fue actualizada."
        messages.success(request, msg)
    else:
        for err in form.non_field_errors():
            messages.error(request, err)
        for field, errs in form.errors.items():
            for err in errs:
                messages.error(request, err)
    return redirect("catalog:product_detail", slug=slug)
