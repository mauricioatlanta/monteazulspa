"""
Pega este contenido en: python manage.py shell (en el servidor donde corre el sitio).
O ejecuta: python manage.py shell < scripts/set_clf02_clf04_notes_now.py

Asigna las notas de compatibilidad a CLF02 y CLF04 en la base de datos actual.
"""
from apps.catalog.models import Product

CLF02_NOTES = """Aplicaciones de referencia (BMW)

Por desplazamiento y configuración del motor.

Desplazamiento   Configuración   Modelos
1.6 – 2.0 L      4 en línea      116i, 118i, 120i, 318i, 320i, X1 sDrive18i
2.5 – 3.0 L      6 en línea      325i, 330i, 523i, 525i, 530i, Z4, X3

Compatibilidad orientativa. Confirmar código de pieza o aplicación exacta antes de comprar."""

CLF04_NOTES = """Años y modelo principal (Chevrolet Cruze)
Este diseño corresponde principalmente a la primera generación del Chevrolet Cruze (J300).
• Años: aproximadamente 2010 hasta 2016.
• Motores: más común en versiones 1.8 L (atmosférico) y en algunas variantes 1.4 L Turbo.
• Nota: En 2016 hubo transición en Chile (Cruze Limited vs. modelo nuevo); si el vehículo es de ese año, conviene verificar si es carrocería antigua o nueva.

Otros modelos que usan el mismo convertidor
Por plataforma Delta II y motorización compartida con General Motors, este catalítico suele ser compatible con:
• Chevrolet Sonic (2012–2017), especialmente con motor 1.8 L.
• Chevrolet Tracker (2013–2016), muchas versiones con la misma configuración de escape frontal.
• Chevrolet Orlando (2011–2015), en versiones a gasolina."""

for sku, notes in [("CLF02", CLF02_NOTES), ("CLF04", CLF04_NOTES)]:
    p = Product.objects.filter(sku=sku).first()
    if p is None:
        print("No existe producto", sku)
        continue
    if not hasattr(p, "compatibility_notes"):
        print("El modelo Product no tiene el campo compatibility_notes. Añádelo en apps/catalog/models.py")
        break
    p.compatibility_notes = notes
    p.save(update_fields=["compatibility_notes"])
    print("OK:", sku, "- notas guardadas. Longitud:", len(notes))

print("Listo. Recarga la ficha del producto en el navegador (Ctrl+F5).")
