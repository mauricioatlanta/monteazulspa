# -*- coding: utf-8 -*-
"""
Traduce nombres de productos de inglés a español chileno.
Reemplaza términos técnicos comunes (Offset, Oval, Inlet, etc.) por su equivalente en español.
Uso: python manage.py translate_products_to_spanish [--dry-run]
"""
import re
from django.core.management.base import BaseCommand
from apps.catalog.models import Product


# Términos en inglés -> español (Chile)
TRANSLATIONS = [
    # Orden: reemplazos más largos primero para no pisar subcadenas
    (r"\bOffset\b", "Desplazado"),
    (r"\bOval\b", "Oval"),
    (r"\bCenter\b", "Centro"),
    (r"\bInlet\b", "Entrada"),
    (r"\bOutlet\b", "Salida"),
    (r"\bInches\b", "pulg"),
    (r"\bInch\b", "pulg"),
    (r"\bStraight\b", "Recto"),
    (r"\bReinforced\b", "Reforzado"),
    (r"\bFlexible\b", "flexible"),  # mantener minúscula en nombres compuestos
    (r"\bExtension\b", "Extensión"),
    (r"\bRound\b", "Redondo"),
    (r"\bDual\b", "Dual"),
    (r"\bSingle\b", "Simple"),
    (r"\bUniversal\b", "Universal"),
    (r"\bDirect\s+Fit\b", "Ajuste directo"),
    (r"\bDirect\s+fit\b", "Ajuste directo"),
    (r"\bClamp\b", "Abrazadera"),
    (r"\bFlange\b", "Brida"),
    (r"\bCatalytic\b", "Catalítico"),
    (r"\bConverter\b", "Convertidor"),
    (r"\bMuffler\b", "Silenciador"),
    (r"\bExhaust\b", "Escape"),
    (r"\bPipe\b", "Tubo"),
    (r"\bTail\s+Pipe\b", "Cola"),
    (r"\bTail\s+pipe\b", "Cola"),
    (r"\bQuality\b", "Calidad"),
    (r"\bSuperior\b", "Superior"),
    (r"\bStock\b", "Stock"),  # se deja igual en Chile a veces
]


class Command(BaseCommand):
    help = "Traduce nombres de productos de inglés a español chileno."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar cambios sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)
        products = Product.objects.filter(is_active=True).order_by("sku")
        updated = 0
        for product in products:
            original = product.name
            new_name = original
            for pattern, replacement in TRANSLATIONS:
                new_name = re.sub(pattern, replacement, new_name, flags=re.IGNORECASE)
            if new_name != original:
                if dry_run:
                    self.stdout.write(f"  {product.sku}: {original!r} -> {new_name!r}")
                else:
                    product.name = new_name
                    product.save(update_fields=["name"])
                updated += 1
        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"DRY RUN: se actualizarían {updated} productos."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Listo: {updated} productos actualizados a español chileno."))
