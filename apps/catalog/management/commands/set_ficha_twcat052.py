# -*- coding: utf-8 -*-
"""
Asigna la ficha técnica oficial al convertidor catalítico TWCAT 052 (200) 16 cm Euro 5.
Opcionalmente reemplaza la imagen con la nueva (--image ruta).
Uso: python manage.py set_ficha_twcat052 [--image /ruta/a/imagen.png] [--dry-run]
"""
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductImage

# SKUs posibles para el producto TWCAT 052 (200) 16 CMS Euro 5 Bencinero
SKUS_TWCAT052_16 = ("TWCAT052-16", "TWCAT052--16", "TWCAT052-16-CMS", "TWCAT052")

FICHA_TECNICA_TWCAT052 = """Este detalle es crucial para el mercado chileno (o países con normativas similares), ya que garantiza que el repuesto es legal para circular y aprobar la revisión técnica.

FICHA TÉCNICA: Convertidor Catalítico Universal TWG

1. Identificación del Producto
Marca: TWG EXHAUST
Modelo: TWCAT 052 (200)
Tipo: Universal
Normativa: Euro 5 (Motores Bencineros)

2. Certificaciones y Homologación
Ministerio de Transportes: Producto Certificado por el Ministerio de Transportes y Telecomunicaciones, cumpliendo con los estándares exigidos para la reposición de convertidores catalíticos.
Norma Internacional: Certificación EPA / OBDII.
Uso Legal: Apto para vehículos que deben renovar su componente de escape y aprobar la medición de gases en Plantas de Revisión Técnica (PRT).

3. Especificaciones Técnicas
Característica - Detalle
Largo del Cuerpo - 16 cm (160 mm)
Compatibilidad - Vehículos livianos y medianos
Tecnología - Monolito cerámico de alta eficiencia
Material - Acero inoxidable de grado automotriz"""


class Command(BaseCommand):
    help = "Asigna ficha técnica al TWCAT 052 (200) 16 cm Euro 5 y opcionalmente actualiza la imagen."

    def add_arguments(self, parser):
        parser.add_argument("--image", type=str, default="", help="Ruta a la imagen para reemplazar la actual.")
        parser.add_argument("--dry-run", action="store_true", help="No guardar cambios.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        image_path = (options.get("image") or "").strip()

        product = None
        for sku in SKUS_TWCAT052_16:
            product = Product.objects.filter(sku=sku, is_active=True).first()
            if product:
                break
        if not product:
            product = Product.objects.filter(sku__icontains="TWCAT052", name__icontains="16").first()
        if not product:
            self.stderr.write(
                self.style.ERROR("No se encontró el producto TWCAT 052 (200) 16 cm. SKUs buscados: " + ", ".join(SKUS_TWCAT052_16))
            )
            return

        self.stdout.write(f"Producto: {product.sku} | {product.name}")

        if not dry_run:
            product.ficha_tecnica = FICHA_TECNICA_TWCAT052
            product.length = 16
            product.euro_norm = "EURO5"
            product.material = "INOX"
            product.save(update_fields=["ficha_tecnica", "length", "euro_norm", "material"])
            product.refresh_quality(save=True)
            self.stdout.write(self.style.SUCCESS("Ficha técnica, largo (16 cm), Euro 5 y material asignados."))
        else:
            self.stdout.write(self.style.WARNING("Dry-run: se asignarían ficha técnica, length=16, euro_norm=EURO5, material=INOX."))

        if image_path:
            path = Path(image_path).resolve()
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Imagen no encontrada: {path}"))
                return
            if dry_run:
                self.stdout.write(self.style.WARNING(f"Dry-run: se reemplazaría la imagen con {path}"))
                return
            existing = product.images.filter(position=1).first()
            if existing:
                existing.delete()
            name = f"twcat052-16-euro5{path.suffix}"
            with open(path, "rb") as f:
                content = ContentFile(f.read(), name=name)
                img = ProductImage(
                    product=product,
                    alt_text="TWCAT 052 (200) 16 CMS Euro 5 Bencinero - TWG Exhaust",
                    is_primary=True,
                    position=1,
                )
                img.image.save(name, content, save=True)
            self.stdout.write(self.style.SUCCESS(f"Imagen actualizada: {img.image.name}"))
        else:
            self.stdout.write("Para cambiar la imagen: python manage.py set_ficha_twcat052 --image /ruta/a/imagen.png")
