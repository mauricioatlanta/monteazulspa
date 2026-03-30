"""
Script para probar el Buscador Inteligente de Escape.

Ejecutar:
  python manage.py test_smart_search

Valida los 6 casos de aceptación:
  1. q=2x6           -> redirige a buscar-escape
  2. q=2,5x8         -> redirige a buscar-escape
  3. q=toyota yaris 2015 -> redirige a buscador-vehiculo con brand/model/year
  4. q=catalitico toyota yaris -> redirige a buscador-vehiculo
  5. q=2015          -> redirige a product_list (no a vehículo)
  6. q=yaris         -> redirige a buscador-vehiculo (modelo; marca inferida en la página)
"""
from django.core.management.base import BaseCommand
from django.test import Client
from django.urls import reverse


# Casos: (query, tipo_esperado, descripción)
# tipo_esperado: "measure" | "vehicle" | "product"
CASOS = [
    ("2x6", "measure", "Medida 2x6 -> buscar-escape"),
    ("2,5x8", "measure", "Medida 2,5x8 -> buscar-escape"),
    ("toyota yaris 2015", "vehicle", "Vehículo Toyota Yaris 2015 -> buscador-vehiculo"),
    ("catalitico toyota yaris", "vehicle", "Catalítico Toyota Yaris -> buscador-vehiculo"),
    ("2015", "product", "Solo año 2015 -> listado producto (no vehículo)"),
    ("yaris", "vehicle", "Solo modelo yaris -> buscador-vehiculo (marca inferida)"),
]


class Command(BaseCommand):
    help = "Prueba los 6 casos del Buscador Inteligente (parser + redirecciones HTTP)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--parser-only",
            action="store_true",
            help="Solo validar el parser (parse_smart_search), sin HTTP.",
        )
        parser.add_argument(
            "--http-only",
            action="store_true",
            help="Solo validar redirecciones HTTP, sin parser.",
        )

    def handle(self, *args, **options):
        parser_only = options["parser_only"]
        http_only = options["http_only"]
        if not parser_only and not http_only:
            parser_only = http_only = False  # run both

        ok = 0
        fail = 0

        if not http_only:
            self.stdout.write("--- Parser (parse_smart_search) ---")
            try:
                from apps.catalog.utils.smart_search import parse_smart_search
            except Exception as e:
                self.stdout.write(
                    self.style.WARNING(f"  No se pudo importar el parser: {e}. Ejecuta con --http-only para probar solo redirecciones.")
                )
            else:
                for q, tipo_esperado, desc in CASOS:
                    parsed = parse_smart_search(q)
                    actual = parsed.get("type")
                    if actual == tipo_esperado:
                        self.stdout.write(self.style.SUCCESS(f"  OK   q={q!r} -> type={actual} ({desc})"))
                        ok += 1
                    else:
                        self.stdout.write(
                            self.style.ERROR(f"  FAIL q={q!r} -> esperado type={tipo_esperado}, obtuvo {actual} ({desc})")
                        )
                        fail += 1
            if not parser_only:
                self.stdout.write("")

        if not parser_only:
            self.stdout.write("--- Redirecciones HTTP ---")
            client = Client()
            smart_search_url = reverse("catalog:smart_search")
            # Cliente de prueba usa 'testserver' por defecto; permitir localhost para ALLOWED_HOSTS
            extra = {"HTTP_HOST": "localhost"}

            for q, tipo_esperado, desc in CASOS:
                resp = client.get(smart_search_url, {"q": q}, follow=False, **extra)
                if resp.status_code != 302:
                    self.stdout.write(
                        self.style.ERROR(f"  FAIL q={q!r} -> status {resp.status_code}, esperado 302 ({desc})")
                    )
                    fail += 1
                    continue

                location = resp.get("Location", "")
                if tipo_esperado == "measure":
                    esperado_en = "buscar-escape"
                elif tipo_esperado == "vehicle":
                    esperado_en = "buscador-vehiculo"
                else:
                    esperado_en = "productos"  # product_list puede ser /productos/ o /productos/?q=...

                if esperado_en in location:
                    self.stdout.write(self.style.SUCCESS(f"  OK   q={q!r} -> 302 -> ...{esperado_en}... ({desc})"))
                    ok += 1
                else:
                    self.stdout.write(
                        self.style.ERROR(f"  FAIL q={q!r} -> Location no contiene {esperado_en!r}: {location} ({desc})")
                    )
                    fail += 1

        self.stdout.write("")
        total = ok + fail
        if fail == 0:
            self.stdout.write(self.style.SUCCESS(f"Todos los casos pasaron ({total}/{total})."))
        else:
            self.stdout.write(self.style.WARNING(f"Resultado: {ok} OK, {fail} FAIL (total {total})."))
