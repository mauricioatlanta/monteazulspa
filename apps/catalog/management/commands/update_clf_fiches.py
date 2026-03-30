# -*- coding: utf-8 -*-
"""
Actualiza las fichas de CLF02 (BMW) y CLF04 (Chevrolet) con las notas de
compatibilidad y, en CLF04, con las ProductCompatibility correctas.

Ejecutar en el mismo entorno (y base de datos) que sirve el sitio:

  python manage.py update_clf_fiches

Para ver qué se haría sin guardar:

  python manage.py update_clf_fiches --dry-run
"""
from django.core.management.base import BaseCommand

from apps.catalog.models import (
    Product,
    ProductCompatibility,
    VehicleBrand,
    VehicleModel,
)

# CLF02 BMW
CLF02_NOTES = """Aplicaciones de referencia (BMW)

Por desplazamiento y configuración del motor.

Desplazamiento   Configuración   Modelos
1.6 – 2.0 L      4 en línea      116i, 118i, 120i, 318i, 320i, X1 sDrive18i
2.5 – 3.0 L      6 en línea      325i, 330i, 523i, 525i, 530i, Z4, X3

Compatibilidad orientativa. Confirmar código de pieza o aplicación exacta antes de comprar."""

# CLF04 Chevrolet Cruze
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

CLF04_APPLICATIONS = [
    ("Cruze", 2010, 2016, "1ª gen J300; 1.8 L y 1.4 T; 2016 verificar carrocería"),
    ("Sonic", 2012, 2017, "Especialmente motor 1.8 L"),
    ("Tracker", 2013, 2016, "Misma configuración escape frontal"),
    ("Orlando", 2011, 2015, "Versiones a gasolina"),
]


class Command(BaseCommand):
    help = "Actualiza notas de compatibilidad en CLF02 y CLF04 (y compatibilidades en CLF04)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guardar cambios.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        if not hasattr(Product, "compatibility_notes"):
            self.stderr.write(
                self.style.ERROR(
                    "El modelo Product no tiene el campo 'compatibility_notes'. "
                    "Ejecuta: python manage.py migrate catalog"
                )
            )
            return

        # --- CLF02 BMW ---
        p02 = Product.objects.filter(sku="CLF02").first()
        if p02:
            if p02.compatibility_notes != CLF02_NOTES:
                if not dry_run:
                    p02.compatibility_notes = CLF02_NOTES
                    p02.save(update_fields=["compatibility_notes"])
                self.stdout.write(self.style.SUCCESS("CLF02: notas de compatibilidad (BMW) actualizadas."))
            else:
                self.stdout.write("CLF02: notas ya estaban definidas.")
        else:
            self.stdout.write(self.style.WARNING("CLF02: producto no encontrado."))

        # --- CLF04 Chevrolet ---
        p04 = Product.objects.filter(sku="CLF04").first()
        if not p04:
            self.stdout.write(self.style.WARNING("CLF04: producto no encontrado."))
            return

        if p04.compatibility_notes != CLF04_NOTES:
            if not dry_run:
                p04.compatibility_notes = CLF04_NOTES
                p04.save(update_fields=["compatibility_notes"])
            self.stdout.write(self.style.SUCCESS("CLF04: notas de compatibilidad actualizadas."))
        else:
            self.stdout.write("CLF04: notas ya estaban definidas.")

        brand = VehicleBrand.objects.filter(name__iexact="Chevrolet").first()
        if not brand:
            if dry_run:
                self.stdout.write("CLF04: se crearía marca Chevrolet.")
            else:
                brand = VehicleBrand.objects.create(name="Chevrolet")
                self.stdout.write(self.style.SUCCESS("CLF04: creada marca Chevrolet."))

        if brand:
            model_objs = {}
            for model_name, y_from, y_to, notes in CLF04_APPLICATIONS:
                m = VehicleModel.objects.filter(brand=brand, name__iexact=model_name).first()
                if not m and not dry_run:
                    m, _ = VehicleModel.objects.get_or_create(brand=brand, name=model_name)
                model_objs[model_name] = m

            created = updated = 0
            for model_name, year_from, year_to, notes in CLF04_APPLICATIONS:
                m = model_objs.get(model_name)
                if not m:
                    continue
                existing = ProductCompatibility.objects.filter(
                    product=p04, brand=brand, model=m, is_active=True
                ).first()
                if existing:
                    if (existing.year_from, existing.year_to, existing.notes) != (year_from, year_to, notes):
                        if not dry_run:
                            existing.year_from = year_from
                            existing.year_to = year_to
                            existing.notes = notes
                            existing.fuel_type = "GASOLINA"
                            existing.save(update_fields=["year_from", "year_to", "notes", "fuel_type"])
                        updated += 1
                else:
                    if not dry_run:
                        ProductCompatibility.objects.create(
                            product=p04,
                            brand=brand,
                            model=m,
                            year_from=year_from,
                            year_to=year_to,
                            fuel_type="GASOLINA",
                            notes=notes,
                            confidence="ALTA",
                            is_active=True,
                        )
                    created += 1
            if created or updated:
                self.stdout.write(self.style.SUCCESS(f"CLF04: {created} compatibilidades creadas, {updated} actualizadas."))

        self.stdout.write("Listo. Recarga la ficha del producto en el navegador (Ctrl+F5 si hace falta).")
