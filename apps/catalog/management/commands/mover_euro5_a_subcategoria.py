# -*- coding: utf-8 -*-
"""
Mueve catalíticos a las subcategorías Euro 3, Euro 4 y Euro 5 según indicadores:
- euro_norm = EURO3/EURO4/EURO5 en la raíz Cataliticos Twc.
- Nombre o alt_text de imagen contiene "euro 3", "euro 4", "euro 5".
- Ruta/nombre de archivo de imagen contiene "euro3", "euro4", "euro5" (o con espacio/guion bajo).

Opciones:
  --list                    Listar todos los catalíticos con imágenes.
  --productos-euro3=SKU,...  Mover esos SKU a Euro 3.
  --productos-euro4=SKU,...  Mover esos SKU a Euro 4.
  --productos-euro5=SKU,...  Mover esos SKU a Euro 5.
Uso: python manage.py mover_euro5_a_subcategoria [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.catalog.models import Product, ProductImage, Category

# (número, euro_norm en BD, etiqueta nombre, slug subcategoría)
EURO_LEVELS = (
    (3, "EURO3", "euro 3", "euro3", "euro_3", "cataliticos-twc-euro3"),
    (4, "EURO4", "euro 4", "euro4", "euro_4", "cataliticos-twc-euro4"),
    (5, "EURO5", "euro 5", "euro5", "euro_5", "cataliticos-twc-euro5"),
)


def _ids_para_euro(cat_twc, cat_dest, category_ids_twc, euro_tuple):
    """Devuelve set de product.id que indican este Euro (euro_norm, nombre, alt_text, ruta imagen)."""
    num, euro_norm_val, label_con_espacio, label_sin_espacio, label_guion, slug_sub = euro_tuple

    ids = set()

    # euro_norm en raíz Cataliticos Twc
    qs = Product.objects.filter(
        category=cat_twc,
        is_active=True,
        deleted_at__isnull=True,
        euro_norm=euro_norm_val,
    )
    ids |= set(qs.values_list("id", flat=True))

    # nombre contiene "euro 3" / "euro 4" / "euro 5"
    qs = Product.objects.filter(
        category_id__in=category_ids_twc,
        is_active=True,
        deleted_at__isnull=True,
        name__icontains=label_con_espacio,
    ).exclude(category=cat_dest)
    ids |= set(qs.values_list("id", flat=True))

    # alt_text de imagen
    images_alt = ProductImage.objects.filter(
        alt_text__icontains=label_con_espacio
    ).values_list("product_id", flat=True)
    qs = Product.objects.filter(
        id__in=images_alt,
        category_id__in=category_ids_twc,
        is_active=True,
        deleted_at__isnull=True,
    ).exclude(category=cat_dest)
    ids |= set(qs.values_list("id", flat=True))

    # ruta/nombre de archivo de imagen
    images_path = ProductImage.objects.filter(
        Q(image__icontains=label_sin_espacio) | Q(image__icontains=label_con_espacio) | Q(image__icontains=label_guion)
    ).values_list("product_id", flat=True)
    ids_ruta = set(Product.objects.filter(
        id__in=images_path,
        is_active=True,
        deleted_at__isnull=True,
    ).exclude(category=cat_dest).values_list("id", flat=True))
    ids_ruta &= set(Product.objects.filter(id__in=ids_ruta, category_id__in=category_ids_twc).values_list("id", flat=True))
    ids |= ids_ruta

    return ids


class Command(BaseCommand):
    help = "Mueve catalíticos a subcategorías Euro 3, Euro 4 y Euro 5 (por euro_norm, nombre, alt_text o ruta de imagen)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Solo listar cambios, no guardar.")
        parser.add_argument(
            "--productos-euro3",
            type=str,
            default="",
            help="SKUs separados por coma para mover a Euro 3.",
        )
        parser.add_argument(
            "--productos-euro4",
            type=str,
            default="",
            help="SKUs separados por coma para mover a Euro 4.",
        )
        parser.add_argument(
            "--productos-euro5",
            type=str,
            default="",
            help="SKUs separados por coma para mover a Euro 5.",
        )
        parser.add_argument(
            "--list",
            action="store_true",
            help="Listar todos los productos Cataliticos Twc con imágenes.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        skus_euro3 = [s.strip() for s in (options.get("productos_euro3") or "").split(",") if s.strip()]
        skus_euro4 = [s.strip() for s in (options.get("productos_euro4") or "").split(",") if s.strip()]
        skus_euro5 = [s.strip() for s in (options.get("productos_euro5") or "").split(",") if s.strip()]
        listar = options.get("list", False)
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        cat_twc = Category.objects.filter(slug="cataliticos-twc", is_active=True).first()
        if not cat_twc:
            self.stderr.write(self.style.ERROR("No existe la categoría Cataliticos TWC. Ejecuta estructura_categorias_cataliticos o reordenar_categorias."))
            return

        cats_euro = {}
        for t in EURO_LEVELS:
            c = Category.objects.filter(slug=t[5], is_active=True).first()
            if not c:
                self.stderr.write(self.style.ERROR(f"Falta la subcategoría {t[5]} (Euro {t[0]}). Ejecuta reordenar_categorias."))
                return
            cats_euro[t[0]] = c

        child_ids = list(Category.objects.filter(parent=cat_twc, is_active=True).values_list("id", flat=True))
        category_ids_twc = [cat_twc.id] + child_ids

        # Modo --list
        if listar:
            productos = (
                Product.objects.filter(
                    category_id__in=category_ids_twc,
                    is_active=True,
                    deleted_at__isnull=True,
                )
                .prefetch_related("images")
                .order_by("category__slug", "sku")
            )
            self.stdout.write(f"Productos Cataliticos Twc con imágenes (total {productos.count()}):")
            for p in productos:
                imgs = list(p.images.all())
                paths = [str(img.image) for img in imgs] if imgs else ["(sin imagen)"]
                self.stdout.write(f"  {p.sku} | {p.name[:45]}... | cat={p.category.name} | imágenes: {paths}")
            return

        # Modo --productos-euro3 / euro4 / euro5: mover por SKU
        for num, _norm, _label, _slug_short, _guion, slug_cat in EURO_LEVELS:
            skus = [skus_euro3, skus_euro4, skus_euro5][num - 3]
            if not skus:
                continue
            cat_dest = cats_euro[num]
            products = Product.objects.filter(
                sku__in=skus,
                is_active=True,
                deleted_at__isnull=True,
            ).exclude(category=cat_dest)
            ids = set(products.values_list("id", flat=True))
            if not ids:
                self.stdout.write(self.style.NOTICE(f"Euro {num}: ningún producto con SKU en {skus} encontrado o ya están en Euro {num}."))
                continue
            self.stdout.write(f"Euro {num}: mover a subcategoría ({len(ids)} productos por SKU)")
            for p in Product.objects.filter(id__in=ids).select_related("category"):
                self.stdout.write(f"  - {p.sku} | {p.name[:50]}... (actual: {p.category.name})")
            if not dry_run:
                Product.objects.filter(id__in=ids).update(category=cat_dest)
                for pid in ids:
                    Product.objects.get(pk=pid).refresh_quality(save=True)
                self.stdout.write(self.style.SUCCESS(f"  Listo: {len(ids)} productos movidos a Euro {num}."))
        if skus_euro3 or skus_euro4 or skus_euro5:
            return

        # Detección automática para Euro 3, Euro 4 y Euro 5
        total_movidos = 0
        for num, euro_norm_val, label_con_espacio, label_sin_espacio, label_guion, slug_sub in EURO_LEVELS:
            cat_dest = cats_euro[num]
            todos_ids = _ids_para_euro(cat_twc, cat_dest, category_ids_twc, (num, euro_norm_val, label_con_espacio, label_sin_espacio, label_guion, slug_sub))
            if not todos_ids:
                continue
            productos = Product.objects.filter(id__in=todos_ids).select_related("category")
            self.stdout.write(f"Euro {num}: productos a mover a subcategoría Euro {num} ({productos.count()})")
            for p in productos:
                self.stdout.write(f"  - {p.sku} | {p.name[:50]}... (actual: {p.category.name})")
            if not dry_run:
                Product.objects.filter(id__in=todos_ids).update(category=cat_dest)
                for pid in todos_ids:
                    Product.objects.get(pk=pid).refresh_quality(save=True)
                total_movidos += len(todos_ids)
            else:
                total_movidos += len(todos_ids)

        if total_movidos == 0:
            self.stdout.write(self.style.NOTICE("No hay productos que mover por euro_norm, nombre o ruta de imagen."))
            self.stdout.write("Para mover por SKU: --productos-euro3=SKU1,... --productos-euro4=... --productos-euro5=...")
            self.stdout.write("Para listar: --list")
        elif dry_run:
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Listo: {total_movidos} productos movidos a sus subcategorías Euro 3/4/5."))
