"""
Cargar ProductCompatibility para Chevrolet Sail 2016.

Uso en Windows PowerShell (desde la raíz del proyecto):
  Get-Content scripts/load_chevrolet_sail_compatibilities.py | python manage.py shell

O abrir shell y pegar el contenido:
  python manage.py shell
  # luego pegar el código de abajo

Nota: confidence usa "ALTA", no 100 (es CharField con opciones).
"""
from django.db.models import Q
from apps.catalog.models import (
    ProductCompatibility,
    VehicleBrand,
    VehicleModel,
    Product,
)

brand = VehicleBrand.objects.get(name__iexact="Chevrolet")
model = VehicleModel.objects.get(name__iexact="Sail", brand=brand)

print("ANTES:", ProductCompatibility.objects.filter(
    brand=brand,
    model=model,
    is_active=True,
).count())

candidatos = Product.objects.filter(
    is_active=True,
    deleted_at__isnull=True,
).filter(
    Q(name__icontains="sail")
    | Q(sku__icontains="sail")
    | Q(category__slug__icontains="direct")
).distinct()

print("CANDIDATOS:", candidatos.count())
for p in candidatos[:30]:
    print(" -", p.id, p.sku, p.name, getattr(p, "stock", None))

for p in candidatos:
    ProductCompatibility.objects.get_or_create(
        product=p,
        brand=brand,
        model=model,
        year_from=2016,
        year_to=2016,
        defaults={
            "is_active": True,
            "confidence": "ALTA",
        },
    )

print("DESPUES:", ProductCompatibility.objects.filter(
    brand=brand,
    model=model,
    is_active=True,
).count())
