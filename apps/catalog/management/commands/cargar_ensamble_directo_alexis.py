# -*- coding: utf-8 -*-
"""
Carga productos de Cataliticos Ensamble Directo (datos Alexis Mahara 6/2/2026).
Uso: python manage.py cargar_ensamble_directo_alexis
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product

# (sku, name) - SKU único, nombre para catálogo (incluye vehículo para SEO)
PRODUCTOS_ENSAMBLE_DIRECTO = [
    ("CLF01", "CLF01 Peugeot"),
    ("CLF02", "CLF02 BMW"),
    ("CLF03", "CLF03 Hyundai"),
    ("CLF04", "CLF04 Chevrolet Cruze"),
    ("CLF005", "CLF005 Honda Accord"),
    ("CLF06", "CLF06 Renault Clio"),
    ("CLF07", "CLF07"),
    ("CLF08", "CLF08 Chevrolet Aveo"),
]

# Texto de ficha técnica específico para algunos SKUs de ensamble directo
FICHA_TECNICA_ENSAMBLE_DIRECTO = {
    "CLF01": (
        "Convertidor catalítico ensamble directo (CLF01) para sistemas Euro 3. "
        "Carcasa cerámica, instalación plug & play sin sensor O2, diámetro 1,75\".\n\n"
        "Listado de vehículos clasificados (referencial)\n\n"
        "Año / Marca / Modelo / Motor\n\n"
        "- Peugeot 206 · 1.4 / 1.6 · 8 válvulas / 16 válvulas\n"
        "- Peugeot 307 · 1.6\n"
        "- Citroën C4 · 1.6\n"
        "- 2003 · Peugeot 306 · 1.6\n"
        "- 2002–2004 · Citroën Xsara · 1.6\n"
        "- Citroën Xsara Picasso · 1.6 · 8 válvulas / 16 válvulas\n"
        "- 2002 · Peugeot Partner · 1.4\n"
        "- 2003 · Peugeot 106 · 1.1 / 1.4\n\n"
        "Resumen de modelos compatibles (rango de años referencial)\n\n"
        "Marca    Modelo         Años (rango real)   Notas / Confianza\n"
        "Peugeot  2008           2013 – 2026         Alta\n"
        "Peugeot  206            1999 – 2012         Alta\n"
        "Peugeot  207            2006 – 2015         Alta\n"
        "Peugeot  208            2012 – 2026         Alta\n"
        "Peugeot  3008           2009 – 2026         Alta\n"
        "Peugeot  307            2001 – 2008         Alta\n"
        "Peugeot  308            2007 – 2021         Alta\n"
        "Peugeot  407            2004 – 2011         Alta\n"
        "Peugeot  408            2010 – 2026         Alta\n"
        "Peugeot  5008           2009 – 2026         Alta\n"
        "Peugeot  508            2011 – 2026         Alta\n"
        "Peugeot  Boxer          1994 – 2026         Alta\n"
        "Peugeot  Expert         1995 – 2026         Alta\n"
        "Peugeot  Partner        1996 – 2018         Alta\n"
        "Peugeot  Partner Tepee  2008 – 2018         Alta\n"
        "Peugeot  RCZ            2010 – 2015         Alta\n"
        "Peugeot  Rifter         2018 – 2026         Alta\n\n"
        "Compatibilidad referencial. Verificar siempre con código de pieza original, "
        "foto y normativa vigente antes de instalar."
    ),
}

PRECIO_DEFAULT = Decimal("170000")  # Actualizar en admin o Excel si aplica


class Command(BaseCommand):
    help = "Carga productos Cataliticos Ensamble Directo (CLF1, CLF02 BMW, CLF03 Hyundai, etc.)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo listar qué se crearía/actualizaría.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        cat = Category.objects.filter(
            slug="cataliticos-ensamble-directo",
            is_active=True,
        ).first()
        if not cat:
            cat = Category.objects.filter(
                name__iexact="Cataliticos Ensamble Directo",
                is_active=True,
            ).first()
        if not cat:
            self.stderr.write(
                self.style.ERROR("No existe la categoría 'Cataliticos Ensamble Directo'. Ejecuta antes: python manage.py reordenar_categorias")
            )
            return

        created = 0
        updated = 0
        for sku, name in PRODUCTOS_ENSAMBLE_DIRECTO:
            slug_base = slugify(sku)[:280]
            slug = slug_base
            n = 0
            while Product.objects.filter(slug=slug).exclude(sku=sku).exists():
                n += 1
                slug = f"{slug_base}-{n}"[:280]

            defaults = {
                "name": name,
                "slug": slug,
                "category": cat,
                "price": PRECIO_DEFAULT,
                "cost_price": Decimal("0"),
                "stock": 0,
                "is_active": True,
                "deleted_at": None,
            }

            ficha = FICHA_TECNICA_ENSAMBLE_DIRECTO.get(sku)
            if ficha:
                defaults["ficha_tecnica"] = ficha
            if dry_run:
                exists = Product.objects.filter(sku=sku).exists()
                self.stdout.write(f"  {'Actualizar' if exists else 'Crear'}: {sku} - {name}")
                continue
            prod, is_new = Product.objects.update_or_create(sku=sku, defaults=defaults)
            if is_new:
                created += 1
            else:
                updated += 1
            prod.refresh_quality(save=True)

        if dry_run:
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar."))
            return
        self.stdout.write(
            self.style.SUCCESS(f"Listo: {created} creados, {updated} actualizados en Cataliticos Ensamble Directo.")
        )
