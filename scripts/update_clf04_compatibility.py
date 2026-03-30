"""
Actualiza CLF04: notas de compatibilidad y ProductCompatibility (Cruze 2010-2016, Sonic, Tracker, Orlando).

Ejecutar desde la raíz del proyecto:

  python manage.py shell < scripts/update_clf04_compatibility.py

O:

  python manage.py shell
  >>> exec(open('scripts/update_clf04_compatibility.py').read())

Antes debe estar aplicada la migración que agrega Product.compatibility_notes:
  python manage.py migrate catalog
"""
from apps.catalog.models import (
    Product,
    ProductCompatibility,
    VehicleBrand,
    VehicleModel,
)

CLF04_SKU = "CLF04"

COMPATIBILITY_NOTES = """Años y modelo principal (Chevrolet Cruze)
Este diseño corresponde principalmente a la primera generación del Chevrolet Cruze (J300).
• Años: aproximadamente 2010 hasta 2016.
• Motores: más común en versiones 1.8 L (atmosférico) y en algunas variantes 1.4 L Turbo.
• Nota: En 2016 hubo transición en Chile (Cruze Limited vs. modelo nuevo); si el vehículo es de ese año, conviene verificar si es carrocería antigua o nueva.

Otros modelos que usan el mismo convertidor
Por plataforma Delta II y motorización compartida con General Motors, este catalítico suele ser compatible con:
• Chevrolet Sonic (2012–2017), especialmente con motor 1.8 L.
• Chevrolet Tracker (2013–2016), muchas versiones con la misma configuración de escape frontal.
• Chevrolet Orlando (2011–2015), en versiones a gasolina."""

# (model_name, year_from, year_to, notes)
APPLICATIONS = [
    ("Cruze", 2010, 2016, "1ª gen J300; 1.8 L y 1.4 T; 2016 verificar carrocería"),
    ("Sonic", 2012, 2017, "Especialmente motor 1.8 L"),
    ("Tracker", 2013, 2016, "Misma configuración escape frontal"),
    ("Orlando", 2011, 2015, "Versiones a gasolina"),
]

product = Product.objects.filter(sku=CLF04_SKU).select_related("category").first()
if not product:
    print("ERROR: No existe producto con SKU", CLF04_SKU)
else:
    print("Producto CLF04 encontrado:", product.name)

    # Notas de compatibilidad (requiere migración 0020)
    if hasattr(Product, "compatibility_notes"):
        product.compatibility_notes = COMPATIBILITY_NOTES
        product.save(update_fields=["compatibility_notes"])
        print("OK: Notas de compatibilidad actualizadas en CLF04.")
    else:
        print("AVISO: Product no tiene campo compatibility_notes. Ejecuta: python manage.py migrate catalog")

    brand = VehicleBrand.objects.filter(name__iexact="Chevrolet").first()
    if not brand:
        brand = VehicleBrand.objects.create(name="Chevrolet")
        print("OK: Creada marca Chevrolet.")
    else:
        print("Marca Chevrolet ya existe.")

    model_objs = {}
    for model_name, year_from, year_to, notes in APPLICATIONS:
        model_obj = VehicleModel.objects.filter(brand=brand, name__iexact=model_name).first()
        if not model_obj:
            model_obj, created = VehicleModel.objects.get_or_create(brand=brand, name=model_name)
            if created:
                print("OK: Creado modelo", model_name)
        model_objs[model_name] = model_obj

    created_count = 0
    updated_count = 0
    for model_name, year_from, year_to, notes in APPLICATIONS:
        model_obj = model_objs[model_name]
        existing = ProductCompatibility.objects.filter(
            product=product, brand=brand, model=model_obj, is_active=True
        ).first()
        if existing:
            if (existing.year_from, existing.year_to, existing.notes) != (year_from, year_to, notes):
                existing.year_from = year_from
                existing.year_to = year_to
                existing.notes = notes
                existing.fuel_type = "GASOLINA"
                existing.save(update_fields=["year_from", "year_to", "notes", "fuel_type"])
                updated_count += 1
                print("OK: Actualizada compatibilidad", model_name, year_from, "-", year_to)
        else:
            ProductCompatibility.objects.create(
                product=product,
                brand=brand,
                model=model_obj,
                year_from=year_from,
                year_to=year_to,
                fuel_type="GASOLINA",
                notes=notes,
                confidence="ALTA",
                is_active=True,
            )
            created_count += 1
            print("OK: Creada compatibilidad", model_name, year_from, "-", year_to)

    print("Listo. Creadas:", created_count, "Actualizadas:", updated_count)
