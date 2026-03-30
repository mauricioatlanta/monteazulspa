# -*- coding: utf-8 -*-
"""
Carga marcas, modelos y motores de vehículos por segmento (escape/flexibles/catalíticos).
Solo agrega lo que no existe; no borra datos.
Fuente: segmentos Camionetas, SUV, Autos de Pasajeros, Comerciales.
Uso: python manage.py load_vehicles_segmento_escape
"""
from django.core.management.base import BaseCommand
from apps.catalog.models import VehicleBrand, VehicleModel, VehicleEngine


# Tipo de combustible en BD vs texto en lista
FUEL_MAP = {
    "BENCINA": "GASOLINA",
    "GASOLINA": "GASOLINA",
    "DIÉSEL": "DIESEL",
    "DIESEL": "DIESEL",
    "HÍBRIDO": "HIBRIDO",
    "HIBRIDO": "HIBRIDO",
}


def _fuel(s):
    s = (s or "").strip().upper()
    for key, value in FUEL_MAP.items():
        if key in s:
            return value
    return None


# Lista: (marca, modelo, lista de (nombre_motor, tipo_combustible))
# Segmento 1: Camionetas (Pick-ups)
SEGMENTO_CAMIONETAS = [
    ("Mitsubishi", "L200", [("2.4/2.5 Diésel", "DIESEL")]),
    ("Toyota", "Hilux", [("2.4/2.8 Diésel", "DIESEL"), ("2.7 Bencina", "GASOLINA")]),
    ("Maxus", "T60", [("2.0/2.8 Diésel", "DIESEL")]),
    ("Great Wall", "Poer", [("2.0 Turbo Diésel", "DIESEL")]),
    ("Ford", "Ranger", [("2.2/3.2/2.0 Diésel", "DIESEL")]),
    ("Nissan", "NP300", [("2.3 Diésel", "DIESEL")]),
    ("Nissan", "Navara", [("2.3 Diésel", "DIESEL")]),
    ("Chevrolet", "Silverado", [("3.0 Diésel", "DIESEL"), ("5.3 V8", "GASOLINA")]),
    ("SsangYong", "Musso", [("2.2 Diésel", "DIESEL")]),
    ("SsangYong", "Actyon Sports", [("2.2 Diésel", "DIESEL")]),
    ("JMC", "Vigus", [("2.4 Diésel", "DIESEL")]),
    ("Ford", "F-150", [("3.5/5.0 Bencina", "GASOLINA")]),
    ("RAM", "700", [("1.3/1.4 Bencina", "GASOLINA")]),
    ("Mazda", "BT-50", [("2.2/3.2 Diésel", "DIESEL")]),
    ("JAC", "T8", [("2.0 Diésel", "DIESEL")]),
]

# Segmento 2: SUV
SEGMENTO_SUV = [
    ("Chery", "Tiggo 2", [("1.5 / 1.0T Bencina", "GASOLINA")]),
    ("Chery", "Tiggo 2 Pro", [("1.5 / 1.0T Bencina", "GASOLINA")]),
    ("MG", "ZS", [("1.5 Bencina", "GASOLINA")]),
    ("MG", "ZX", [("1.5 Bencina", "GASOLINA")]),
    ("Chevrolet", "Groove", [("1.5 Bencina", "GASOLINA")]),
    ("Mazda", "CX-5", [("2.0/2.2/2.5 Bencina/Diésel", "GASOLINA"), ("2.0/2.2/2.5 Diésel", "DIESEL")]),
    ("Toyota", "RAV4", [("2.0/2.5 Bencina", "GASOLINA"), ("2.0/2.5 Híbrido", "HIBRIDO")]),
    ("Hyundai", "Tucson", [("2.0 Bencina", "GASOLINA"), ("2.0 Diésel", "DIESEL")]),
    ("Kia", "Sportage", [("2.0 Bencina", "GASOLINA"), ("2.0 Diésel", "DIESEL")]),
    ("Nissan", "Kicks", [("1.6 Bencina", "GASOLINA")]),
    ("Haval", "Jolion", [("1.5 Turbo Bencina", "GASOLINA")]),
    ("Toyota", "Corolla Cross", [("1.8 Híbrido", "HIBRIDO"), ("2.0 Bencina", "GASOLINA")]),
    ("Ford", "Territory", [("1.5/1.8 Turbo Bencina", "GASOLINA")]),
    ("Suzuki", "Vitara", [("1.6 Bencina", "GASOLINA"), ("1.4 Turbo", "GASOLINA")]),
    ("Subaru", "Forester", [("2.0/2.5 Bencina", "GASOLINA")]),
    ("Peugeot", "2008", [("1.2 Turbo Bencina", "GASOLINA"), ("1.5 Diésel", "DIESEL")]),
    ("Peugeot", "3008", [("1.2 Turbo Bencina", "GASOLINA"), ("1.5 Diésel", "DIESEL")]),
    ("Changan", "CX70", [("1.6 Bencina", "GASOLINA")]),
    ("JAC", "JS2", [("1.5 Bencina", "GASOLINA")]),
    ("Toyota", "Raize", [("1.2 Bencina", "GASOLINA")]),
]

# Segmento 3: Autos de Pasajeros (Sedán/Hatchback)
SEGMENTO_AUTOS = [
    ("Suzuki", "Baleno", [("1.4 Bencina", "GASOLINA")]),
    ("Kia", "Soluto", [("1.4 Bencina", "GASOLINA")]),
    ("Chevrolet", "Sail", [("1.4/1.5 Bencina", "GASOLINA")]),
    ("Suzuki", "Swift", [("1.2 Bencina", "GASOLINA")]),
    ("Hyundai", "Grand i10", [("1.0/1.2 Bencina", "GASOLINA")]),
    ("Kia", "Morning", [("1.0/1.2 Bencina", "GASOLINA")]),
    ("Toyota", "Yaris", [("1.5 Bencina", "GASOLINA")]),
    ("Hyundai", "Accent", [("1.4/1.6 Bencina", "GASOLINA")]),
    ("Nissan", "Versa", [("1.6 Bencina", "GASOLINA")]),
    ("Kia", "Rio", [("1.4/1.6 Bencina", "GASOLINA")]),
    ("MG", "3", [("1.5 Bencina", "GASOLINA")]),
    ("Citroën", "C-Elysée", [("1.6 Diésel", "DIESEL"), ("1.6 Bencina", "GASOLINA")]),
    ("Peugeot", "208", [("1.2 Bencina", "GASOLINA"), ("1.5 Diésel", "DIESEL")]),
    ("Suzuki", "S-Presso", [("1.0 Bencina", "GASOLINA")]),
    ("Volkswagen", "Voyage", [("1.6 Bencina", "GASOLINA")]),
    ("Volkswagen", "Gol", [("1.6 Bencina", "GASOLINA")]),
]

# Segmento 4: Comerciales
SEGMENTO_COMERCIALES = [
    ("Peugeot", "Partner", [("1.6 Diésel", "DIESEL")]),
    ("Citroën", "Berlingo", [("1.6 Diésel", "DIESEL")]),
    ("Hyundai", "Porter", [("2.5 Diésel", "DIESEL")]),
    ("Kia", "Frontier", [("2.5 Diésel", "DIESEL")]),
    ("Chevrolet", "N400 Max", [("1.5 Bencina", "GASOLINA")]),
]

ALL_ENTRIES = (
    SEGMENTO_CAMIONETAS
    + SEGMENTO_SUV
    + SEGMENTO_AUTOS
    + SEGMENTO_COMERCIALES
)


class Command(BaseCommand):
    help = "Carga marcas, modelos y motores por segmento escape (solo agrega lo que no existe)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se crearía, sin escribir en la BD.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se escribirá en la BD."))

        created_brands = 0
        created_models = 0
        created_engines = 0

        for brand_name, model_name, engines in ALL_ENTRIES:
            brand_name = brand_name.strip()
            model_name = model_name.strip()
            if not brand_name or not model_name:
                continue

            if not dry_run:
                brand, brand_created = VehicleBrand.objects.get_or_create(name=brand_name)
                if brand_created:
                    created_brands += 1
                model, model_created = VehicleModel.objects.get_or_create(
                    brand=brand,
                    name=model_name,
                )
                if model_created:
                    created_models += 1
                for engine_name, fuel_type in engines:
                    engine_name = engine_name.strip()
                    if not engine_name:
                        continue
                    fuel = fuel_type if fuel_type in ("GASOLINA", "DIESEL", "HIBRIDO", "EV") else _fuel(fuel_type)
                    _, engine_created = VehicleEngine.objects.get_or_create(
                        model=model,
                        name=engine_name,
                        defaults={"fuel_type": fuel},
                    )
                    if engine_created:
                        created_engines += 1
            else:
                created_engines += sum(1 for e, _ in engines if (e or "").strip())

        if dry_run:
            unique_brands = len({e[0].strip() for e in ALL_ENTRIES if e[0].strip()})
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry-run: {len(ALL_ENTRIES)} modelos, {unique_brands} marcas, "
                    f"{created_engines} motores en la lista (no se escribe en la BD)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Listo: {created_brands} marcas nuevas, {created_models} modelos nuevos, "
                    f"{created_engines} motores nuevos. Total: {VehicleBrand.objects.count()} marcas, "
                    f"{VehicleModel.objects.count()} modelos, {VehicleEngine.objects.count()} motores."
                )
            )
