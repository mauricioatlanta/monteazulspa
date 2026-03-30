# -*- coding: utf-8 -*-
"""
Completa la ficha del producto CLF04 (Chevrolet Cruze) con:
- Notas de compatibilidad (años, generación J300, motores, otros modelos).
- ProductCompatibility con años correctos (Cruze 2010-2016) y otros modelos
  (Sonic, Tracker, Orlando) para mejorar la búsqueda por vehículo.

Uso:
  python manage.py set_clf04_compatibility
  python manage.py set_clf04_compatibility --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

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


class Command(BaseCommand):
    help = "Completa CLF04 con notas de compatibilidad y aplicaciones Cruze/Sonic/Tracker/Orlando."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="No guardar cambios; solo mostrar lo que se haría.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        product = Product.objects.filter(sku=CLF04_SKU).select_related("category").first()
        if not product:
            self.stderr.write(self.style.ERROR(f"No existe producto con SKU {CLF04_SKU}."))
            return

        brand = VehicleBrand.objects.filter(name__iexact="Chevrolet").first()
        if not brand:
            if dry_run:
                self.stdout.write("Se crearía la marca Chevrolet.")
                return
            brand = VehicleBrand.objects.create(name="Chevrolet")
            self.stdout.write(self.style.SUCCESS("Creada marca Chevrolet."))

        # get_or_create modelos
        models_created = []
        model_objs = {}
        for model_name, year_from, year_to, notes in APPLICATIONS:
            model_obj = VehicleModel.objects.filter(brand=brand, name__iexact=model_name).first()
            if not model_obj:
                if dry_run:
                    self.stdout.write(f"Se crearía el modelo Chevrolet {model_name}.")
                    continue
                model_obj, created = VehicleModel.objects.get_or_create(
                    brand=brand, name=model_name
                )
                if created:
                    models_created.append(model_name)
            model_objs[model_name] = model_obj

        if models_created and not dry_run:
            self.stdout.write(self.style.SUCCESS(f"Modelos creados: {', '.join(models_created)}."))

        # Notas de compatibilidad
        if product.compatibility_notes != COMPATIBILITY_NOTES:
            if dry_run:
                self.stdout.write("Se actualizaría product.compatibility_notes para CLF04.")
            else:
                product.compatibility_notes = COMPATIBILITY_NOTES
                product.save(update_fields=["compatibility_notes"])
                self.stdout.write(self.style.SUCCESS("Actualizadas notas de compatibilidad en CLF04."))
        else:
            self.stdout.write("Notas de compatibilidad ya estaban definidas.")

        # ProductCompatibility: actualizar Cruze existente o crear todas
        created_count = 0
        updated_count = 0
        for model_name, year_from, year_to, notes in APPLICATIONS:
            model_obj = model_objs.get(model_name)
            if not model_obj and dry_run:
                continue
            if not model_obj:
                continue
            existing = ProductCompatibility.objects.filter(
                product=product,
                brand=brand,
                model=model_obj,
                is_active=True,
            ).first()
            if existing:
                if (existing.year_from, existing.year_to, existing.notes) != (year_from, year_to, notes):
                    if dry_run:
                        self.stdout.write(
                            f"Se actualizaría {model_name}: {existing.year_from}-{existing.year_to} -> {year_from}-{year_to}, notes."
                        )
                    else:
                        existing.year_from = year_from
                        existing.year_to = year_to
                        existing.notes = notes
                        existing.fuel_type = "GASOLINA" if model_name != "Orlando" else "GASOLINA"
                        existing.save(update_fields=["year_from", "year_to", "notes", "fuel_type"])
                        updated_count += 1
            else:
                if dry_run:
                    self.stdout.write(f"Se crearía compatibilidad: Chevrolet {model_name} {year_from}-{year_to}.")
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

        if not dry_run:
            if created_count:
                self.stdout.write(self.style.SUCCESS(f"Creadas {created_count} compatibilidades."))
            if updated_count:
                self.stdout.write(self.style.SUCCESS(f"Actualizadas {updated_count} compatibilidades."))
        self.stdout.write("Listo.")
