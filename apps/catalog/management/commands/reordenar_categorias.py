"""
Ajusta categorías del catálogo según especificación:
- Elimina categoría "Cataliticos Clf" (productos pasan a Cataliticos TWG).
- Renombra "Cataliticos Tipo Original" -> "Cataliticos Ensamble Directo".
- "Cataliticos TWG" tiene subcategorías Euro3, Euro4, Euro5, Diesel.
- Elimina "Tubos flexibles" (productos pasan a Flexibles).
- Agrega categoría "Resonadores".
"""
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.catalog.models import Category, Product


class Command(BaseCommand):
    help = "Reordena y renombra categorías del catálogo (Clf, Tipo Original, Twc, Tubos flexibles, Resonadores)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se haría, sin guardar.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        if dry_run:
            self.stdout.write(self.style.WARNING("Modo dry-run: no se guardarán cambios."))

        # 1) Eliminar "Cataliticos Clf": mover productos a Cataliticos TWG y desactivar
        cat_clf = Category.objects.filter(slug="cataliticos-clf").first()
        if not cat_clf:
            cat_clf = Category.objects.filter(name__iexact="Cataliticos CLF").first()
        cat_twc = Category.objects.filter(slug="cataliticos-twc").first()
        if not cat_twc:
            cat_twc = Category.objects.filter(name__iexact="Cataliticos TWC").first()

        if cat_clf:
            n = cat_clf.products.count()
            if n and cat_twc:
                if not dry_run:
                    cat_clf.products.update(category=cat_twc)
                self.stdout.write(
                    self.style.SUCCESS(f"Cataliticos Clf: {n} productos movidos a Cataliticos TWG.")
                )
            if not dry_run:
                cat_clf.is_active = False
                cat_clf.save(update_fields=["is_active"])
            self.stdout.write("  Categoría 'Cataliticos Clf' desactivada.")
        else:
            self.stdout.write(self.style.NOTICE("  No se encontró categoría Cataliticos Clf."))

        # 2) Renombrar "Cataliticos Tipo Original" -> "Cataliticos Ensamble Directo" y poner como hija de Cataliticos
        cat_tipo = Category.objects.filter(
            slug="cataliticos-tipo-original", parent__isnull=True
        ).first()
        if not cat_tipo:
            cat_tipo = Category.objects.filter(
                name__iexact="Cataliticos Tipo Original", parent__isnull=True
            ).first()
        if not cat_tipo:
            # Por si ya fue renombrada: buscar por slug actual
            cat_tipo = Category.objects.filter(slug="cataliticos-ensamble-directo").first()
        cat_cataliticos_root = Category.objects.filter(slug="cataliticos", parent__isnull=True).first()
        if not cat_cataliticos_root:
            cat_cataliticos_root = Category.objects.filter(name__iexact="Cataliticos", parent__isnull=True).first()
        if cat_tipo:
            new_name = "Cataliticos Ensamble Directo"
            new_slug = "cataliticos-ensamble-directo"
            if not dry_run:
                cat_tipo.name = new_name
                cat_tipo.slug = new_slug
                update_fields = ["name", "slug"]
                if cat_cataliticos_root and cat_tipo.parent_id != cat_cataliticos_root.id:
                    cat_tipo.parent = cat_cataliticos_root
                    update_fields.append("parent")
                cat_tipo.save(update_fields=update_fields)
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Renombrado a: {new_name} (slug: {new_slug})"
                    + (f", parent=Cataliticos" if cat_cataliticos_root else "")
                )
            )
        else:
            # Crear "Cataliticos Ensamble Directo" como hija de Cataliticos si no existe
            if cat_cataliticos_root:
                en_directo, created = Category.objects.get_or_create(
                    slug="cataliticos-ensamble-directo",
                    defaults={
                        "name": "Cataliticos Ensamble Directo",
                        "parent": cat_cataliticos_root,
                        "is_active": True,
                    },
                )
                if not dry_run and created:
                    self.stdout.write(
                        self.style.SUCCESS("  Creada subcategoría: Cataliticos Ensamble Directo (parent: Cataliticos)")
                    )
                elif not dry_run and (en_directo.parent_id != cat_cataliticos_root.id or not en_directo.is_active):
                    en_directo.parent = cat_cataliticos_root
                    en_directo.is_active = True
                    en_directo.save(update_fields=["parent", "is_active"])
                    self.stdout.write(
                        self.style.SUCCESS("  Actualizada: Cataliticos Ensamble Directo, parent=Cataliticos")
                    )
                elif dry_run:
                    self.stdout.write(
                        self.style.SUCCESS("  [dry-run] Se crearía subcategoría: Cataliticos Ensamble Directo bajo Cataliticos")
                    )
            else:
                self.stdout.write(self.style.NOTICE("  No se encontró 'Cataliticos Tipo Original' ni 'Cataliticos Ensamble Directo'; tampoco hay raíz Cataliticos para crearla."))

        # 3) Cataliticos TWG: subcategorías Euro3, Euro4, Euro5, Diesel
        if not cat_twc:
            cat_twc = Category.objects.filter(name__iexact="Cataliticos TWG").first()
            if not cat_twc:
                cat_twc = Category.objects.filter(name__iexact="Cataliticos TWC").first()
        if cat_twc:
            for label, slug_suffix in (("Euro 3", "euro3"), ("Euro 4", "euro4"), ("Euro 5", "euro5"), ("Diesel", "diesel")):
                slug_child = f"cataliticos-twc-{slug_suffix}"
                if dry_run:
                    exists = Category.objects.filter(slug=slug_child).exists()
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  Subcategoría Cataliticos TWG: {label} ({slug_child})"
                            + (" [ya existe]" if exists else " [se crearía]")
                        )
                    )
                    continue
                child, created = Category.objects.get_or_create(
                    slug=slug_child,
                    defaults={
                        "name": label,
                        "parent": cat_twc,
                        "is_active": True,
                    },
                )
                if not created and child.parent_id != cat_twc.id:
                    child.parent = cat_twc
                    child.save(update_fields=["parent"])
                self.stdout.write(
                    self.style.SUCCESS(f"  Subcategoría Cataliticos TWG: {label} ({slug_child})")
                )
        else:
            self.stdout.write(self.style.NOTICE("  No se encontró 'Cataliticos TWG' para subcategorías."))

        # 4) Eliminar "Tubos flexibles": mover productos a Flexibles y desactivar
        cat_tubos = Category.objects.filter(
            slug="tubos-flexibles", parent__isnull=True
        ).first()
        if not cat_tubos:
            cat_tubos = Category.objects.filter(
                name__iexact="Tubos flexibles", parent__isnull=True
            ).first()
        cat_flex = Category.objects.filter(slug="flexibles", parent__isnull=True).first()
        if not cat_flex:
            cat_flex = Category.objects.filter(
                name__iexact="Flexibles", parent__isnull=True
            ).first()

        if cat_tubos:
            n = cat_tubos.products.count()
            if n and cat_flex:
                if not dry_run:
                    cat_tubos.products.update(category=cat_flex)
                self.stdout.write(
                    self.style.SUCCESS(f"Tubos flexibles: {n} productos movidos a Flexibles.")
                )
            elif n and not cat_flex:
                self.stdout.write(
                    self.style.WARNING("  No hay categoría Flexibles; productos quedan en Tubos flexibles.")
                )
            if not dry_run:
                cat_tubos.is_active = False
                cat_tubos.save(update_fields=["is_active"])
            self.stdout.write("  Categoría 'Tubos flexibles' desactivada.")
        else:
            self.stdout.write(self.style.NOTICE("  No se encontró categoría Tubos flexibles."))

        # 5) Agregar Resonadores (slug resonadores para compatibilidad con Excel/import)
        name_res = "Resonadores"
        slug_res = "resonadores"
        if dry_run:
            exists = Category.objects.filter(slug=slug_res).exists()
            self.stdout.write(
                self.style.SUCCESS(
                    f"  Categoría {name_res}" + (" [ya existe]" if exists else " [se crearía]")
                )
            )
        else:
            res, created = Category.objects.get_or_create(
                slug=slug_res,
                defaults={"name": name_res, "parent": None, "is_active": True},
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"  Categoría creada: {name_res}"))
            else:
                if not res.is_active:
                    res.is_active = True
                    res.save(update_fields=["is_active"])
                self.stdout.write(self.style.SUCCESS(f"  Categoría ya existe: {name_res}"))

        if dry_run:
            self.stdout.write(self.style.WARNING("Ejecuta sin --dry-run para aplicar cambios."))
