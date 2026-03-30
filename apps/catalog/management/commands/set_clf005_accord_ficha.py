# -*- coding: utf-8 -*-
"""
CLF005 Honda Accord: compatibilidades correctas para búsqueda por vehículo
y ficha (Accord 1998–2002, Odyssey, Acura CL/TL).

  python manage.py set_clf005_accord_ficha
  python manage.py set_clf005_accord_ficha --dry-run
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.catalog.models import Product, ProductCompatibility, VehicleBrand, VehicleModel

APPLICATIONS = [
    # brand_name, model_name, year_from, year_to, notes
    ("Honda", "Accord", 1998, 2002, "6ª gen; DX/LX/EX/SE; sedán/coupé; F23 2.3L / J30 3.0L V6"),
    ("Honda", "Odyssey", 1999, 2004, "V6 3.5L; mismo diseño físico que Accord 98–02"),
    ("Acura", "CL", 2001, 2003, "V6 3.2L"),
    ("Acura", "TL", 2002, 2003, "V6 3.2L"),
]

FICHA_CLF005 = """Referencia OEM: 18160-PAA-305 (sustituye 18160-PAA-L10, L11, PAB-L00, etc.). Suele estar estampado en el cuerpo del catalítico (18160-PAA-xxx).

Tipo: catalítico de 3 vías, cerámico; 1–2 bung sensor O2 post-cat. Cuerpo acero inoxidable, bridas acero. Posición: bajo piso (converter principal, tras downpipe, antes del silenciador). No es el integrado en colector de modelos más nuevos.

Normativa: EPA OBD-II (1996+). Versiones ULEV vs. estándar pueden variar sustrato; cuerpo y montajes equivalentes.

Conexiones: brida entrada curva + brida salida cónica con soporte lateral 2 agujeros (según diseño de esta referencia).

No intercambiable con Accord 2003–2007, 2008–2017 ni posteriores (diseño distinto, a menudo integrado en colector)."""


class Command(BaseCommand):
    help = "Actualiza ProductCompatibility de CLF005 (Accord 98–02, Odyssey, Acura CL/TL)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry = options["dry_run"]
        p = Product.objects.filter(sku="CLF005").first()
        if not p:
            self.stderr.write(self.style.ERROR("No existe CLF005."))
            return
        if dry:
            self.stdout.write("Dry-run: se desactivarían compat. actuales y se crearían 4 filas.")
            return
        with transaction.atomic():
            ProductCompatibility.objects.filter(product=p).update(is_active=False)
            for bname, mname, yf, yt, notes in APPLICATIONS:
                brand, _ = VehicleBrand.objects.get_or_create(name=bname)
                model, _ = VehicleModel.objects.get_or_create(brand=brand, name=mname)
                ProductCompatibility.objects.create(
                    product=p,
                    brand=brand,
                    model=model,
                    year_from=yf,
                    year_to=yt,
                    notes=notes,
                    confidence="ALTA",
                    fuel_type="GASOLINA",
                    is_active=True,
                )
            base = (p.ficha_tecnica or "").strip()
            if "18160-PAA-305" not in base:
                p.ficha_tecnica = (base + "\n\n" + FICHA_CLF005).strip() if base else FICHA_CLF005
                p.save(update_fields=["ficha_tecnica"])
        self.stdout.write(self.style.SUCCESS("CLF005: 4 compatibilidades activas + ficha técnica actualizada."))
