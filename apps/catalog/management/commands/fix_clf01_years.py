from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductCompatibility


RANGE_BY_MODEL = {
    "2008": (2013, 2026),
    "206": (1999, 2012),
    "207": (2006, 2015),
    "208": (2012, 2026),
    "3008": (2009, 2026),
    "307": (2001, 2008),
    "308": (2007, 2021),
    "407": (2004, 2011),
    "408": (2010, 2026),
    "5008": (2009, 2026),
    "508": (2011, 2026),
    "Boxer": (1994, 2026),
    "Expert": (1995, 2026),
    "Partner": (1996, 2018),
    "Partner Tepee": (2008, 2018),
    "RCZ": (2010, 2015),
    "Rifter": (2018, 2026),
}


class Command(BaseCommand):
    help = "Corrige rangos de años de compatibilidad para CLF01 Peugeot"

    def handle(self, *args, **options):
        try:
            product = Product.objects.get(sku="CLF01")
        except Product.DoesNotExist:
            self.stderr.write(self.style.ERROR("No se encontró producto CLF01"))
            return

        qs = ProductCompatibility.objects.filter(
            product=product,
            brand__name__iexact="Peugeot",
            is_active=True,
        ).select_related("model")

        total = qs.count()
        self.stdout.write(f"Encontradas {total} compatibilidades Peugeot activas para CLF01")

        updated = 0
        for pc in qs:
            model_name = pc.model.name if pc.model else ""
            year_range = RANGE_BY_MODEL.get(model_name)
            if not year_range:
                self.stdout.write(f"  [SIN CAMBIO] {model_name or '—'} {pc.year_from}-{pc.year_to}")
                continue

            year_from, year_to = year_range
            pc.year_from = year_from
            pc.year_to = year_to
            pc.save(update_fields=["year_from", "year_to"])
            updated += 1
            self.stdout.write(f"  [OK] {model_name}: {year_from}-{year_to}")

        self.stdout.write(self.style.SUCCESS(f"Listo: {updated} compatibilidades actualizadas."))

