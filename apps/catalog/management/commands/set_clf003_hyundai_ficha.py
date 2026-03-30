from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Product, ProductCompatibility, VehicleBrand, VehicleModel


APPLICATIONS = [
    # brand_name, model_name, year_from, year_to, notes
    ("Hyundai", "Accent", 2012, 2019, "RB 4ª gen; motor Gamma 1.6 L MPI"),
    ("Hyundai", "Elantra", 2011, 2016, "MD/UD 5ª gen; motores Gamma/Nu 1.6–2.0 L"),
    ("Hyundai", "Veloster", 2012, 2017, "1ª gen; motor Gamma 1.6 L MPI/GDI"),
    ("Kia", "Rio", 2012, 2017, "UB 3ª gen; motor Gamma 1.6 L MPI"),
    ("Kia", "Soul", 2012, 2019, "AM/PS 1ª–2ª gen; Gamma 1.6 L y Nu 2.0 L"),
    ("Kia", "Forte", 2014, 2018, "YD 2ª gen; Nu 1.8/2.0 L y Gamma 1.6 L"),
]


FICHA_CLF03 = """Aplicaciones de referencia (Hyundai / Kia, 4 cilindros en línea)

Convertidor catalítico de 3 vías integrado en el múltiple de escape (manifold catalytic converter),
para motores de 4 cilindros en línea con brida de entrada de 4 agujeros (culata de 4 puertos).
Diseño típico de motores Gamma 1.6 L y Nu 1.8 / 2.0 L atmosféricos.

Modelos y años frecuentes

- Hyundai Accent 2012–2019 (RB, 4ª gen.) – Motor 1.6 L Gamma MPI.
- Hyundai Elantra / Avante 2011–2016 (MD/UD, 5ª gen.) – Motores 1.6 / 1.8 / 2.0 L Gamma / Nu.
- Hyundai Veloster 2012–2017 (1ª gen.) – Motor 1.6 L Gamma MPI / GDI.
- Kia Rio 2012–2017 (UB, 3ª gen.) – Motor 1.6 L Gamma MPI.
- Kia Soul 2012–2019 (AM/PS, 1ª–2ª gen.) – Motores 1.6 L Gamma y 2.0 L Nu.
- Kia Forte / Cerato 2014–2018 (YD, 2ª gen.) – Motores 1.8 / 2.0 L Nu y 1.6 L Gamma.

En algunos mercados este manifold se mantiene hasta aprox. 2019 en versiones base (Euro 4 / Euro 5).

Datos técnicos

- Tipo: catalizador de 3 vías integrado en múltiple de escape (close-coupled / manifold converter).
- Motores compatibles: Gamma 1.6 L (MPI / GDI) y Nu 1.8 / 2.0 L (MPI / GDI).
- Brida de entrada: 4 agujeros para culata de 4 cilindros en línea.
- Posición: frontal, a la salida directa del motor (pre-catalizador principal).
- Sensores O2: normalmente 1–2 roscas (sensor aguas arriba antes del catalizador y aguas abajo después).
- Normativa típica: EPA federal y Euro 4 / Euro 5 (según mercado y año).
- Intercambiabilidad: alta entre Accent, Rio, Soul y Veloster 1.6 L; media con Elantra / Forte (pueden variar curvas del múltiple o longitud total, verificar antes de montar).

Compatibilidad orientativa. Confirmar siempre código de pieza, fotos de múltiple y normativa local antes de comprar."""


class Command(BaseCommand):
    help = "Actualiza compatibilidades y ficha técnica de CLF03 (Hyundai/Kia Gamma/Nu)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="No guardar cambios.")

    def handle(self, *args, **options):
        dry = options["dry_run"]

        product = Product.objects.filter(sku="CLF03").first()
        if not product:
            self.stderr.write(self.style.ERROR("No existe producto con SKU CLF03."))
            return

        if dry:
            self.stdout.write(
                "Dry-run: se desactivarían compatibilidades actuales de CLF03 "
                "y se crearían/actualizarían filas para Accent, Elantra, Veloster, Rio, Soul y Forte."
            )
            return

        with transaction.atomic():
            # Desactivar compatibilidades antiguas
            ProductCompatibility.objects.filter(product=product).update(is_active=False)

            created = 0
            for brand_name, model_name, year_from, year_to, notes in APPLICATIONS:
                brand, _ = VehicleBrand.objects.get_or_create(name=brand_name)
                model, _ = VehicleModel.objects.get_or_create(brand=brand, name=model_name)
                ProductCompatibility.objects.create(
                    product=product,
                    brand=brand,
                    model=model,
                    year_from=year_from,
                    year_to=year_to,
                    notes=notes,
                    confidence="ALTA",
                    fuel_type="GASOLINA",
                    is_active=True,
                )
                created += 1

            # Ficha técnica: anexar solo si aún no se ha agregado este bloque
            base = (product.ficha_tecnica or "").strip()
            if "Aplicaciones de referencia (Hyundai / Kia, 4 cilindros en línea)" not in base:
                product.ficha_tecnica = (base + "\n\n" + FICHA_CLF03).strip() if base else FICHA_CLF03
                product.save(update_fields=["ficha_tecnica"])

        self.stdout.write(
            self.style.SUCCESS(
                f"CLF03: {created} compatibilidades activas creadas y ficha técnica actualizada."
            )
        )

