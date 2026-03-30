from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import VehicleBrand, VehicleModel, VehicleEngine


PEUGEOT_DATA = [
    {
        "model": "404",
        "year_from": 1970,
        "year_to": 1980,
        "engines": [
            {"code": "XC6 / XC7", "cc": 1618, "fuel": "GASOLINA", "label": "1.6 XC6 / XC7"},
        ],
    },
    {
        "model": "504",
        "year_from": 1970,
        "year_to": 1987,
        "engines": [
            {"code": "XM7 / XN1", "cc": 1796, "fuel": "GASOLINA", "label": "1.8 XM7 / XN1"},
            {"code": "XM7 / XN1", "cc": 1971, "fuel": "GASOLINA", "label": "2.0 XM7 / XN1"},
        ],
    },
    {
        "model": "504 Diesel",
        "year_from": 1978,
        "year_to": 1987,
        "engines": [
            {"code": "XD2", "cc": 2304, "fuel": "DIESEL", "label": "2.3 XD2 Diesel"},
        ],
    },
    {
        "model": "505",
        "year_from": 1980,
        "year_to": 1991,
        "engines": [
            {"code": "XN1", "cc": 1971, "fuel": "GASOLINA", "label": "2.0 XN1"},
            {"code": "ZNJK (V6)", "cc": 2849, "fuel": "GASOLINA", "label": "2.8 V6 ZNJK"},
        ],
    },
    {
        "model": "205",
        "year_from": 1984,
        "year_to": 1998,
        "engines": [
            {"code": "TU1", "cc": 1124, "fuel": "GASOLINA", "label": "1.1 TU1"},
            {"code": "TU3", "cc": 1360, "fuel": "GASOLINA", "label": "1.4 TU3"},
            {"code": "XU9", "cc": 1905, "fuel": "GASOLINA", "label": "1.9 XU9"},
        ],
    },
    {
        "model": "405",
        "year_from": 1988,
        "year_to": 1999,
        "engines": [
            {"code": "XU5", "cc": 1580, "fuel": "GASOLINA", "label": "1.6 XU5"},
            {"code": "XU9", "cc": 1905, "fuel": "GASOLINA", "label": "1.9 XU9"},
            {"code": "XU10", "cc": 1998, "fuel": "GASOLINA", "label": "2.0 XU10"},
        ],
    },
    {
        "model": "106",
        "year_from": 1992,
        "year_to": 2003,
        "engines": [
            {"code": "TU1", "cc": 1124, "fuel": "GASOLINA", "label": "1.1 TU1"},
            {"code": "TU3", "cc": 1360, "fuel": "GASOLINA", "label": "1.4 TU3"},
            {"code": "TU5", "cc": 1587, "fuel": "GASOLINA", "label": "1.6 TU5"},
        ],
    },
    {
        "model": "306",
        "year_from": 1994,
        "year_to": 2002,
        "engines": [
            {"code": "TU3", "cc": 1360, "fuel": "GASOLINA", "label": "1.4 TU3"},
            {"code": "TU5", "cc": 1587, "fuel": "GASOLINA", "label": "1.6 TU5"},
            {"code": "XU10", "cc": 1998, "fuel": "GASOLINA", "label": "2.0 XU10"},
            {"code": "XUD9", "cc": 1905, "fuel": "DIESEL", "label": "1.9 XUD9 Diesel"},
        ],
    },
    {
        "model": "Partner",
        "year_from": 1996,
        "year_to": 2026,
        "engines": [
            {"code": "TU3", "cc": 1360, "fuel": "GASOLINA", "label": "1.4 TU3"},
            {"code": "DW8", "cc": 1868, "fuel": "DIESEL", "label": "1.9 DW8 Diesel"},
            {"code": "DV6", "cc": 1560, "fuel": "DIESEL", "label": "1.6 HDi DV6"},
        ],
    },
    {
        "model": "206",
        "year_from": 1999,
        "year_to": 2012,
        "engines": [
            {"code": "TU3", "cc": 1360, "fuel": "GASOLINA", "label": "1.4 TU3"},
            {"code": "TU5", "cc": 1587, "fuel": "GASOLINA", "label": "1.6 TU5"},
            {"code": "DV4", "cc": 1398, "fuel": "DIESEL", "label": "1.4 HDi DV4"},
        ],
    },
    {
        "model": "307",
        "year_from": 2001,
        "year_to": 2011,
        "engines": [
            {"code": "TU5JP4", "cc": 1587, "fuel": "GASOLINA", "label": "1.6 TU5JP4"},
            {"code": "EW10", "cc": 1997, "fuel": "GASOLINA", "label": "2.0 EW10"},
        ],
    },
    {
        "model": "407",
        "year_from": 2004,
        "year_to": 2011,
        "engines": [
            {"code": "EW10", "cc": 1997, "fuel": "GASOLINA", "label": "2.0 EW10"},
            {"code": "EW12", "cc": 2230, "fuel": "GASOLINA", "label": "2.2 EW12"},
            {"code": "DW10", "cc": 1997, "fuel": "DIESEL", "label": "2.0 DW10 Diesel"},
        ],
    },
    {
        "model": "308",
        "year_from": 2007,
        "year_to": 2026,
        "engines": [
            {"code": "EP6", "cc": 1598, "fuel": "GASOLINA", "label": "1.6 EP6 / THP"},
            {"code": "EB2", "cc": 1199, "fuel": "GASOLINA", "label": "1.2 PureTech EB2"},
            {"code": "DV6", "cc": 1560, "fuel": "DIESEL", "label": "1.6 HDi DV6"},
        ],
    },
    {
        "model": "207 Compact",
        "year_from": 2008,
        "year_to": 2014,
        "engines": [
            {"code": "TU3", "cc": 1360, "fuel": "GASOLINA", "label": "1.4 TU3"},
            {"code": "TU5", "cc": 1587, "fuel": "GASOLINA", "label": "1.6 TU5"},
            {"code": "DV4", "cc": 1398, "fuel": "DIESEL", "label": "1.4 HDi DV4"},
        ],
    },
    {
        "model": "3008",
        "year_from": 2010,
        "year_to": 2026,
        "engines": [
            {"code": "EP6 (THP)", "cc": 1598, "fuel": "GASOLINA", "label": "1.6 THP EP6"},
            {"code": "DV6", "cc": 1560, "fuel": "DIESEL", "label": "1.6 HDi DV6"},
        ],
    },
    {
        "model": "208",
        "year_from": 2012,
        "year_to": 2026,
        "engines": [
            {"code": "EB2 (PureTech)", "cc": 1199, "fuel": "GASOLINA", "label": "1.2 PureTech EB2"},
            {"code": "DV6", "cc": 1560, "fuel": "DIESEL", "label": "1.6 HDi DV6"},
        ],
    },
    {
        "model": "301",
        "year_from": 2012,
        "year_to": 2024,
        "engines": [
            {"code": "EC5 (VTi)", "cc": 1587, "fuel": "GASOLINA", "label": "1.6 VTi EC5"},
            {"code": "DV6", "cc": 1560, "fuel": "DIESEL", "label": "1.6 HDi DV6"},
        ],
    },
    {
        "model": "2008",
        "year_from": 2013,
        "year_to": 2026,
        "engines": [
            {"code": "EB2", "cc": 1199, "fuel": "GASOLINA", "label": "1.2 PureTech EB2"},
            {"code": "DV5 (BlueHDi)", "cc": 1499, "fuel": "DIESEL", "label": "1.5 BlueHDi DV5"},
        ],
    },
    {
        "model": "Rifter",
        "year_from": 2018,
        "year_to": 2026,
        "engines": [
            {"code": "EB2", "cc": 1199, "fuel": "GASOLINA", "label": "1.2 PureTech EB2"},
            {"code": "DV5", "cc": 1499, "fuel": "DIESEL", "label": "1.5 BlueHDi DV5"},
        ],
    },
    {
        "model": "Landtrek",
        "year_from": 2020,
        "year_to": 2026,
        "engines": [
            {"code": "D20", "cc": 1910, "fuel": "DIESEL", "label": "1.9 D20 Diesel"},
            {"code": "4K22", "cc": 2378, "fuel": "GASOLINA", "label": "2.4 4K22"},
        ],
    },
]


def build_engine_name(item):
    liters = round(item["cc"] / 1000, 1)
    liters_txt = str(liters).replace(".0", "")
    fuel_label = "Diésel" if item["fuel"] == "DIESEL" else "Gasolina"
    return f'{liters_txt}L {item["code"]} ({fuel_label})'


class Command(BaseCommand):
    help = "Carga estructura Peugeot de modelos y motores para el buscador por vehículo."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra lo que haría sin guardar cambios.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        brand, _ = VehicleBrand.objects.get_or_create(name="Peugeot")

        models_created = 0
        engines_created = 0
        engines_updated = 0

        for row in PEUGEOT_DATA:
            model, model_created = VehicleModel.objects.get_or_create(
                brand=brand,
                name=row["model"],
            )
            if model_created:
                models_created += 1

            for eng in row["engines"]:
                engine_name = build_engine_name(eng)

                obj, created = VehicleEngine.objects.get_or_create(
                    model=model,
                    name=engine_name,
                    defaults={
                        "fuel_type": eng["fuel"],
                        "displacement_cc": eng["cc"],
                    },
                )

                if created:
                    engines_created += 1
                else:
                    changed = False
                    if obj.fuel_type != eng["fuel"]:
                        obj.fuel_type = eng["fuel"]
                        changed = True
                    if obj.displacement_cc != eng["cc"]:
                        obj.displacement_cc = eng["cc"]
                        changed = True
                    if changed:
                        obj.save(update_fields=["fuel_type", "displacement_cc"])
                        engines_updated += 1

        if dry_run:
            raise RuntimeError("Dry run ejecutado, rollback intencional.")

        self.stdout.write(self.style.SUCCESS("Peugeot cargado correctamente"))
        self.stdout.write(f"Modelos creados: {models_created}")
        self.stdout.write(f"Motores creados: {engines_created}")
        self.stdout.write(f"Motores actualizados: {engines_updated}")

