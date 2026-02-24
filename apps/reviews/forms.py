from django import forms
from .models import Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["rating", "title", "body"]
        widgets = {
            "rating": forms.Select(choices=[(i, f"{i} estrella{'s' if i > 1 else ''}") for i in range(1, 6)]),
            "title": forms.TextInput(attrs={"placeholder": "Título (opcional)", "maxlength": 120}),
            "body": forms.Textarea(attrs={"placeholder": "Cuéntanos tu experiencia con el producto...", "rows": 4}),
        }
