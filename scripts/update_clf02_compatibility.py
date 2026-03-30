"""
Actualiza CLF02 (BMW): incorpora en la ficha técnica la tabla de aplicaciones
por desplazamiento y configuración del motor.

Ejecutar desde la raíz del proyecto:

  python manage.py shell < scripts/update_clf02_compatibility.py

O:

  python manage.py shell
  >>> exec(open('scripts/update_clf02_compatibility.py').read())

Requiere migración que agrega Product.compatibility_notes aplicada:
  python manage.py migrate catalog
"""
from apps.catalog.models import Product

CLF02_SKU = "CLF02"

COMPATIBILITY_NOTES = """Aplicaciones de referencia (BMW)

Por desplazamiento y configuración del motor.

Desplazamiento   Configuración   Modelos
1.6 – 2.0 L      4 en línea      116i, 118i, 120i, 318i, 320i, X1 sDrive18i
2.5 – 3.0 L      6 en línea      325i, 330i, 523i, 525i, 530i, Z4, X3

Compatibilidad orientativa. Confirmar código de pieza o aplicación exacta antes de comprar."""

product = Product.objects.filter(sku=CLF02_SKU).select_related("category").first()
if not product:
    print("ERROR: No existe producto con SKU", CLF02_SKU)
else:
    print("Producto CLF02 encontrado:", product.name)
    if hasattr(Product, "compatibility_notes"):
        product.compatibility_notes = COMPATIBILITY_NOTES
        product.save(update_fields=["compatibility_notes"])
        print("OK: Notas de compatibilidad (BMW) actualizadas en CLF02.")
    else:
        print("AVISO: Product no tiene campo compatibility_notes. Ejecuta: python manage.py migrate catalog")
    print("Listo.")
