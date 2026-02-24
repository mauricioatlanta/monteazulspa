"""
Formularios para administración de productos (Centro de Operaciones).
"""
from django import forms
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet
from django.forms import inlineformset_factory

from .models import Product, ProductImage, Category


class ProductAdminForm(forms.ModelForm):
    """ModelForm para editar producto: nombre, precio, descripción, categoría, stock, etc."""

    class Meta:
        model = Product
        fields = [
            "name",
            "sku",
            "slug",
            "category",
            "price",
            "cost_price",
            "stock",
            "stock_minimum_alert",
            "ficha_tecnica",
            "is_active",
            "euro_norm",
            "combustible",
            "material",
            "install_type",
            "diametro_entrada",
            "diametro_salida",
            "largo_mm",
            "tiene_sensor",
            "celdas",
            "weight",
            "length",
            "width",
            "height",
            "volume",
            "has_warranty",
            "warranty_days",
            "warranty_terms",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre del producto"}),
            "sku": forms.TextInput(attrs={"class": "form-control", "placeholder": "Código SKU"}),
            "slug": forms.TextInput(attrs={"class": "form-control", "placeholder": "slug-url"}),
            "category": forms.Select(attrs={"class": "form-control"}),
            "price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "cost_price": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "stock": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "stock_minimum_alert": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "ficha_tecnica": forms.Textarea(attrs={"class": "form-control", "rows": 6}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "euro_norm": forms.Select(attrs={"class": "form-control"}),
            "combustible": forms.Select(attrs={"class": "form-control"}),
            "material": forms.Select(attrs={"class": "form-control"}),
            "install_type": forms.Select(attrs={"class": "form-control"}),
            "diametro_entrada": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "pulg."}),
            "diametro_salida": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0", "placeholder": "pulg."}),
            "largo_mm": forms.NumberInput(attrs={"class": "form-control", "min": "0", "placeholder": "mm"}),
            "tiene_sensor": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "celdas": forms.NumberInput(attrs={"class": "form-control", "min": "0", "placeholder": "CPSI"}),
            "weight": forms.NumberInput(attrs={"class": "form-control", "step": "0.001", "min": "0"}),
            "length": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "width": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "height": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "min": "0"}),
            "volume": forms.NumberInput(attrs={"class": "form-control", "step": "0.0001", "min": "0"}),
            "has_warranty": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "warranty_days": forms.NumberInput(attrs={"class": "form-control", "min": "0"}),
            "warranty_terms": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }

    def clean_price(self):
        value = self.cleaned_data.get("price")
        if value is not None and value < 0:
            raise forms.ValidationError("El precio debe ser mayor o igual a 0.")
        return value

    def clean_cost_price(self):
        value = self.cleaned_data.get("cost_price")
        if value is not None and value < 0:
            raise forms.ValidationError("El costo debe ser mayor o igual a 0.")
        return value

    def clean_stock(self):
        value = self.cleaned_data.get("stock")
        if value is not None and value < 0:
            raise forms.ValidationError("El stock no puede ser negativo.")
        return value


class ProductImageForm(forms.ModelForm):
    """Form para una imagen de producto (galería)."""

    class Meta:
        model = ProductImage
        fields = ["image", "alt_text", "is_primary", "position"]
        widgets = {
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/*"}),
            "alt_text": forms.TextInput(attrs={"class": "form-control", "placeholder": "Texto alternativo"}),
            "is_primary": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "position": forms.NumberInput(attrs={"class": "form-control", "min": 1, "max": 4}),
        }


class BaseProductImageFormSet(BaseInlineFormSet):
    """Valida posiciones únicas 1-4 y que solo haya una imagen principal."""

    def clean(self):
        super().clean()
        positions = []
        primary_count = 0
        primary_form = None
        primary_old_pos = None

        for form in self.forms:
            if not getattr(form, "cleaned_data", None):
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            img = form.cleaned_data.get("image")
            pos = form.cleaned_data.get("position")
            is_primary = form.cleaned_data.get("is_primary")

            # Si el usuario dejó una fila vacía (nueva sin imagen), ignórala
            if not img and not form.instance.pk:
                continue

            # Fila con imagen o existente debe tener posición 1-4
            if pos is None:
                raise ValidationError(
                    "Indica la posición (1–4) para cada imagen."
                )
            if pos < 1 or pos > 4:
                raise ValidationError(
                    f"Posición {pos} no válida. Usa valores entre 1 y 4."
                )
            if pos in positions:
                raise ValidationError(
                    f"Posición repetida: {pos}. Usa 1–4 sin repetir."
                )
            positions.append(pos)

            if is_primary:
                primary_count += 1
                primary_form = form
                primary_old_pos = pos

        if primary_count > 1:
            raise ValidationError("Solo puedes marcar UNA imagen como Principal.")

        # Regla dura: imagen principal siempre en posición 1 (intercambiar con la que tenía 1)
        if primary_form and primary_old_pos != 1:
            primary_form.cleaned_data["position"] = 1
            for form in self.forms:
                if not getattr(form, "cleaned_data", None) or form.cleaned_data.get("DELETE"):
                    continue
                if form is primary_form:
                    continue
                if form.cleaned_data.get("position") == 1:
                    form.cleaned_data["position"] = primary_old_pos
                    break


# Formset para hasta 4 imágenes por producto (ProductImage.MAX_IMAGES_PER_PRODUCT = 4)
ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    form=ProductImageForm,
    formset=BaseProductImageFormSet,
    extra=1,
    max_num=ProductImage.MAX_IMAGES_PER_PRODUCT,
    can_delete=True,
    validate_max=True,
)
