# -*- coding: utf-8 -*-
"""
Carga marcas y modelos de vehículos del mercado chileno (años 80 en adelante).
Uso: python manage.py load_vehicles_chile
"""
from django.core.management.base import BaseCommand
from apps.catalog.models import VehicleBrand, VehicleModel


# Marcas y modelos representativos del mercado chileno (1980 en adelante)
VEHICLES_CHILE = {
    "Chevrolet": [
        "Corsa", "Corsa Classic", "Spark", "Onix", "Prisma", "Aveo", "Cruze",
        "Captiva", "Tracker", "Equinox", "S10", "Colorado", "LUV", "Silverado",
        "Monza", "Kadett", "Celebrity", "Corsa Pick Up", "Niva", "D-Max",
    ],
    "Toyota": [
        "Corolla", "Yaris", "Etios", "Camry", "Avalon", "Hilux", "Fortuner",
        "RAV4", "Land Cruiser", "Prado", "C-HR", "Innova", "Hiace", "Dyna",
        "Tercel", "Tercel", "Starlet", "Celica", "Supra", "4Runner",
    ],
    "Nissan": [
        "Versa", "March", "Tiida", "Sentra", "Altima", "X-Trail", "Kicks",
        "Qashqai", "Patrol", "Navara", "Frontier", "NP300", "Murano",
        "Sunny", "Tsuru", "Platina", "Pick Up", "Terrano", "Pathfinder",
    ],
    "Hyundai": [
        "i10", "i20", "Accent", "Elantra", "Sonata", "Tucson", "Santa Fe",
        "Creta", "Kona", "Porter", "H-100", "Starex", "Grand i10", "i30",
        "Genesis", "Veloster", "Terracan",
    ],
    "Kia": [
        "Picanto", "Rio", "Cerato", "Optima", "Sportage", "Sorento", "Stonic",
        "Seltos", "Niro", "Carnival", "Bongo", "K2700", "Pride", "Besta",
    ],
    "Suzuki": [
        "Alto", "Swift", "Baleno", "Celerio", "Vitara", "Jimny", "Grand Vitara",
        "Ertiga", "APV", "Carry", "Samurai", "Sidekick", "SX4", "Ignis",
    ],
    "Mazda": [
        "2", "3", "6", "CX-3", "CX-5", "CX-30", "CX-9", "BT-50", "626",
        "323", "Protege", "Demio", "Tribute", "MPV", "B-series",
    ],
    "Ford": [
        "Ka", "Fiesta", "Focus", "Mondeo", "Ranger", "Everest", "Explorer",
        "EcoSport", "Territory", "Maverick", "F-150", "Transit", "Courier",
        "Escort", "Orion", "Laser", "Taurus", "Explorer Sport Trac",
    ],
    "Volkswagen": [
        "Gol", "Golf", "Polo", "Vento", "Passat", "Jetta", "Tiguan", "T-Cross",
        "Taos", "Amarok", "Saveiro", "Transporter", "Beetle", "Fox", "Up!",
        "Pointer", "Santana", "Quantum", "Caravelle", "Caddy",
    ],
    "Honda": [
        "Fit", "City", "Civic", "Accord", "HR-V", "CR-V", "Pilot", "BR-V",
        "Jazz", "Legend", "NSX", "Ridgeline", "Acty", "Stepwagon",
    ],
    "Mitsubishi": [
        "L200", "Lancer", "Outlander", "ASX", "Pajero", "Pajero Sport",
        "Montero", "Eclipse", "Galant", "Colt", "Triton", "Space Star",
        "Eclipse Cross", "Xpander", "L300", "Pajero IO",
    ],
    "Fiat": [
        "Uno", "Palio", "Siena", "Strada", "Doblo", "Punto", "Linea",
        "Toro", "Cronos", "Argo", "Mobi", "500", "Panda", "Ducato",
        "Brava", "Bravo", "Stilo", "Idea", "Grande Punto",
    ],
    "Renault": [
        "Kwid", "Sandero", "Logan", "Clio", "Symbol", "Megane", "Fluence",
        "Duster", "Koleos", "Captur", "Oroch", "Kangoo", "Master", "Trafic",
        "9", "11", "12", "18", "19", "21", "Scenic",
    ],
    "Peugeot": [
        "208", "308", "408", "508", "2008", "3008", "5008", "Partner",
        "Expert", "Boxer", "206", "207", "307", "407", "Partner Tepee",
        "RCZ", "Rifter",
    ],
    "Citroën": [
        "C3", "C4", "C4 Cactus", "C5", "Berlingo", "C-Elysée", "Aircross",
        "C3 Aircross", "Xsara", "Saxo", "ZX", "BX", "AX", "Evasion",
    ],
    "Chery": [
        "Tiggo 2", "Tiggo 3", "Tiggo 4", "Tiggo 5", "Tiggo 7", "Tiggo 8",
        "Arrizo 5", "QQ", "Fulwin", "Cowin", "OMODA 5",
    ],
    "JAC": [
        "J2", "J3", "J4", "J5", "J6", "T40", "T50", "T60", "S2", "S3", "S4",
        "S5", "Sei", "Refine", "Sunray", "Hunter",
    ],
    "MG": [
        "3", "5", "ZS", "HS", "RX5", "Marvel R", "EHS",
    ],
    "BYD": [
        "Yuan Plus", "Song Plus", "Tang", "Han", "Dolphin", "Seal", "e6",
    ],
    "Geely": [
        "Coolray", "Azkarra", "Emgrand", "Atlas", "Geometry C",
    ],
    "SsangYong": [
        "Korando", "Rexton", "Tivoli", "Musso", "Actyon", "Kyron", "Stavic",
    ],
    "Isuzu": [
        "D-Max", "MU-X", "NQR", "FRR", "Pick Up", "Trooper", "Rodeo",
    ],
    "Jeep": [
        "Renegade", "Compass", "Cherokee", "Grand Cherokee", "Wrangler",
        "Gladiator", "Commander", "Patriot",
    ],
    "Dodge": [
        "Journey", "Durango", "Ram", "Dart", "Charger", "Challenger", "Caliber",
    ],
    "Chrysler": [
        "PT Cruiser", "Sebring", "300C", "Voyager", "Pacifica",
    ],
    "Subaru": [
        "XV", "Forester", "Outback", "Impreza", "Legacy", "WRX", "BRZ",
    ],
    "BMW": [
        "Serie 1", "Serie 2", "Serie 3", "Serie 5", "X1", "X2", "X3", "X4", "X5",
    ],
    "Mercedes-Benz": [
        "Clase A", "Clase B", "Clase C", "Clase E", "GLA", "GLB", "GLC", "GLE",
    ],
    "Audi": [
        "A3", "A4", "A5", "A6", "Q3", "Q5", "Q7", "Q2",
    ],
    "Volvo": [
        "S60", "S90", "XC40", "XC60", "XC90", "V60", "V90",
    ],
    "Land Rover": [
        "Defender", "Discovery", "Discovery Sport", "Range Rover", "Range Rover Evoque",
        "Range Rover Sport", "Range Rover Velar",
    ],
    "Mini": [
        "Cooper", "Countryman", "Clubman", "Paceman",
    ],
    "Dacia": [
        "Sandero", "Logan", "Duster", "Spring", "Jogger",
    ],
    "Great Wall": [
        "Haval H6", "Poer", "Cannon", "Wingle", "Steed",
    ],
}


class Command(BaseCommand):
    help = "Carga marcas y modelos de vehículos del mercado chileno (1980 en adelante)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Borrar todas las marcas/modelos antes de cargar (opcional).",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            deleted_m = VehicleModel.objects.count()
            deleted_b = VehicleBrand.objects.count()
            VehicleModel.objects.all().delete()
            VehicleBrand.objects.all().delete()
            self.stdout.write(f"Eliminados: {deleted_b} marcas, {deleted_m} modelos.")

        created_brands = 0
        created_models = 0

        for brand_name, model_names in sorted(VEHICLES_CHILE.items()):
            brand, created = VehicleBrand.objects.get_or_create(name=brand_name)
            if created:
                created_brands += 1
            for model_name in model_names:
                _, created = VehicleModel.objects.get_or_create(
                    brand=brand,
                    name=model_name.strip(),
                )
                if created:
                    created_models += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Listo: {created_brands} marcas nuevas, {created_models} modelos nuevos. "
                f"Total: {VehicleBrand.objects.count()} marcas, {VehicleModel.objects.count()} modelos."
            )
        )
