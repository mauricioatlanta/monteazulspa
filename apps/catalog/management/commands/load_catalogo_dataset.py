# -*- coding: utf-8 -*-
"""
Carga productos desde un archivo JSON o CSV (dataset maestro) al catálogo.

Reglas de formato aplicadas:
- Nomenclatura: [CATEGORÍA] [PART#] - [DESCRIPCIÓN/VEHÍCULO]
- Unidades: Medidas en pulgadas (") y cm en descripción; peso_kg y largo_m como numéricos.
- Largo: Se convierte de metros a cm para el campo length.
- Material: Se mapea a ACERO, INOX o CERAMICO según tipo.
- Tipo Original: Nombre incluye marca/modelo para SEO.
- Todo en español técnico automotriz.

Uso:
    python manage.py load_catalogo_dataset misc/catalogo_dataset.json
    python manage.py load_catalogo_dataset misc/datos.csv --dry-run
"""
import csv
import json
import re
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.text import slugify

from apps.catalog.models import Category, Product

# Mapeo: categoría del dataset -> slug de categoría
CATEGORIA_TO_SLUG = {
    "silenciador": "silenciadores",
    "silenciadores": "silenciadores",
    "flexible": "flexibles",
    "flexibles": "flexibles",
    "catalítico clf": "cataliticos-twc",
    "catalitico clf": "cataliticos-twc",
    "catalítico twc": "cataliticos-twc",
    "catalitico twc": "cataliticos-twc",
    "tipo original": "cataliticos-ensamble-directo",
    "catalíticos tipo original": "cataliticos-ensamble-directo",
    "cola escape": "colas-de-escape",
    "colas de escape": "colas-de-escape",
    "resonador": "resonadores",
    "resonadores": "resonadores",
}

# Mapeo material/tipo -> modelo Product.material
MATERIAL_MAP = {
    "acero aluminizado": "ACERO",
    "acero": "ACERO",
    "inoxidable": "INOX",
    "inoxidable ss409": "INOX",
    "inoxidable ss": "INOX",
    "malla inox c/interlock": "INOX",
    "malla inox": "INOX",
    "cerámico": "CERAMICO",
    "ceramico": "CERAMICO",
    "metálico": "INOX",
    "metalico": "INOX",
    "acero inox pulido": "INOX",
    "acero inox": "INOX",
}

# Euro norm en descripción/material
EURO_PATTERNS = [
    (r"euro\s*5|euro5", "EURO5"),
    (r"euro\s*4|euro4", "EURO4"),
    (r"euro\s*3|euro3", "EURO3"),
]


def _normalize_key(s):
    """Clave normalizada para mapeos."""
    if not s:
        return ""
    return re.sub(r"\s+", " ", str(s).strip().lower())


def _to_decimal(val):
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return Decimal(str(val))
    s = str(val).strip().replace(",", ".")
    try:
        n = re.sub(r"[^\d.-]", "", s) or "0"
        return Decimal(n) if n else None
    except Exception:
        return None


def _resolve_material(text):
    """Extrae material del texto y lo mapea al valor del modelo."""
    if not text:
        return None
    t = _normalize_key(text)
    for key, val in MATERIAL_MAP.items():
        if key in t:
            return val
    return None


def _resolve_euro_norm(text):
    """Extrae Euro 3/4/5 del texto."""
    if not text:
        return None
    t = (text or "").lower()
    for pattern, euro in EURO_PATTERNS:
        if re.search(pattern, t):
            return euro
    return None


# Nombres amigables para categorías que se crean si no existen
SLUG_TO_NAME = {
    "silenciadores": "Silenciadores de Alto Flujo",
    "flexibles": "Flexibles",
    "cataliticos-twc": "Catalíticos TWG",
    "cataliticos-ensamble-directo": "Catalíticos Ensamble Directo",
    "colas-de-escape": "Colas de Escape",
    "resonadores": "Resonadores",
}


def _resolve_category(categoria):
    """Devuelve Category para la categoría del dataset. Crea la categoría si no existe."""
    key = _normalize_key(categoria)
    slug = CATEGORIA_TO_SLUG.get(key)
    if not slug:
        return None
    cat = Category.objects.filter(slug=slug, is_active=True).first()
    if cat:
        return cat
    # Crear categoría si existe en nuestro mapeo pero no en BD
    name = SLUG_TO_NAME.get(slug, slug.replace("-", " ").title())
    cat, _ = Category.objects.get_or_create(
        slug=slug,
        defaults={"name": name, "is_active": True, "parent": None},
    )
    return cat


def _get_euro_subcategory(categoria, descripcion, euro_norm):
    """Para Catalíticos TWG, intenta asignar subcategoría Euro 3/4/5 o Diesel."""
    key = _normalize_key(categoria)
    if "clf" in key:
        return Category.objects.filter(slug="cataliticos-twc-euro3", is_active=True).first()
    if "twc" in key and euro_norm:
        child = Category.objects.filter(
            slug=f"cataliticos-twc-{euro_norm.lower()}", is_active=True
        ).first()
        if child:
            return child
    euro = euro_norm or _resolve_euro_norm(descripcion)
    if euro:
        child = Category.objects.filter(
            slug=f"cataliticos-twc-{euro.lower()}", is_active=True
        ).first()
        if child:
            return child
    return Category.objects.filter(slug="cataliticos-twc", is_active=True).first()


def build_product_name(categoria, part_number, descripcion, es_tipo_original=False):
    """
    Construye nombre según: [CATEGORÍA] [PART#] - [DESCRIPCIÓN/VEHÍCULO].
    Para Tipo Original se prioriza marca/modelo en la descripción para SEO.
    """
    cat = (categoria or "").strip()
    part = (part_number or "").strip().upper()
    desc = (descripcion or "").strip()
    parts = []
    if cat:
        parts.append(cat)
    if part:
        parts.append(part)
    name = " ".join(parts)
    if desc:
        name = f"{name} - {desc}" if name else desc
    return name[:255] if name else (part or "Sin nombre")


def process_row(row):
    """
    Procesa una fila del JSON/CSV y devuelve dict con campos para Product.
    row: dict con keys en español o inglés.
    """
    def _get(*keys, default=""):
        for k in keys:
            v = row.get(k)
            if v is not None and str(v).strip() != "":
                return v
        return default

    categoria = _get("categoria", "Categoría", default="")
    part = _get("part_number", "Part#", "part#", default="")
    desc = _get("descripcion", "Descripción / Medidas (In & Cm)", "Descripción", default="")
    material_tipo = _get("material_tipo", "Material / Tipo", "Material", default="")
    largo_m = _get("largo_m", "Largo (Mts)", "largo_mts", "Largo", default=None)
    peso_kg = _get("peso_kg", "Peso Est. (Kg)", "peso_est_kg", "Peso", default=None)
    precio = _get("precio", "Precio", default=0)

    sku = (part or "").strip().upper()
    if not sku:
        return None

    # Normalizar descripción para mantener medidas en " y cm
    desc_clean = (desc or "").strip()

    es_tipo_original = "tipo original" in _normalize_key(categoria)
    name = build_product_name(categoria, part, desc_clean, es_tipo_original)

    # Categoría
    base_cat = _resolve_category(categoria)
    if not base_cat:
        base_cat = Category.objects.filter(slug="silenciadores", is_active=True).first()
    euro_norm = _resolve_euro_norm(desc_clean) or _resolve_euro_norm(material_tipo)
    if base_cat and base_cat.slug == "cataliticos-twc":
        cat = _get_euro_subcategory(categoria, desc_clean, euro_norm) or base_cat
    else:
        cat = base_cat

    # Peso y largo (conversión m -> cm)
    weight = _to_decimal(peso_kg)
    length_m = _to_decimal(largo_m)
    length_cm = (length_m * 100) if length_m is not None else None

    material = _resolve_material(material_tipo) or _resolve_material(desc_clean)
    price = _to_decimal(precio) or Decimal("0")

    # Ficha técnica: material y medidas en español
    ficha_parts = []
    if material_tipo:
        ficha_parts.append(f"Material/Tipo: {material_tipo.strip()}")
    if desc_clean and desc_clean != material_tipo:
        ficha_parts.append(f"Medidas/Descripción: {desc_clean}")
    ficha = "\n".join(ficha_parts) if ficha_parts else ""

    return {
        "sku": sku,
        "name": name,
        "category": cat,
        "price": price,
        "weight": weight,
        "length": length_cm,
        "material": material,
        "euro_norm": euro_norm,
        "ficha_tecnica": ficha or None,
    }


class Command(BaseCommand):
    help = "Carga productos desde archivo JSON (dataset maestro) con reglas de nomenclatura y unidades."

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            type=str,
            help="Ruta al archivo .json del dataset (ej: misc/catalogo_dataset.json)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Solo mostrar qué se importaría, sin guardar.",
        )

    def _load_rows(self, path):
        """Carga filas desde JSON o CSV."""
        path = Path(path).resolve()
        suffix = path.suffix.lower()
        if suffix == ".csv":
            rows = []
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Normalizar keys (quitar espacios, mantener compatibilidad)
                    normalized = {}
                    for k, v in row.items():
                        key = (k or "").strip()
                        if key:
                            normalized[key] = v
                    rows.append(normalized)
            return rows
        # JSON
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rows = data.get("productos", data) if isinstance(data, dict) else data
        if not isinstance(rows, list):
            raise ValueError("El JSON debe contener una lista de productos.")
        return rows

    def handle(self, path, dry_run, **options):
        path = Path(path).resolve()
        if not path.exists():
            base = Path(__file__).resolve().parents[2]
            candidates = [
                path,
                Path.cwd() / path.name,
                base / "misc" / path.name,
                base / path.name,
            ]
            for c in candidates:
                if c.exists():
                    path = c
                    break
            if not path.exists():
                self.stderr.write(self.style.ERROR(f"Archivo no encontrado: {path}"))
                return

        self.stdout.write(f"Leyendo {path} ...")
        try:
            rows = self._load_rows(path)
        except json.JSONDecodeError as e:
            self.stderr.write(self.style.ERROR(f"JSON inválido: {e}"))
            return
        except ValueError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        created = 0
        updated = 0
        skipped = 0

        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                skipped += 1
                continue
            parsed = process_row(row)
            if not parsed or not parsed.get("sku"):
                skipped += 1
                continue

            cat = parsed.get("category")
            if not cat:
                self.stdout.write(
                    self.style.WARNING(f"  [{parsed['sku']}] Sin categoría, omitido.")
                )
                skipped += 1
                continue

            if dry_run:
                dims = []
                if parsed.get("weight"):
                    dims.append(f"peso={parsed['weight']}kg")
                if parsed.get("length"):
                    dims.append(f"largo={parsed['length']}cm")
                dims_str = " | " + ", ".join(dims) if dims else ""
                self.stdout.write(
                    f"  {parsed['sku']} | {parsed['name'][:50]}... | "
                    f"{parsed['price']} | {cat.slug}{dims_str}"
                )
                continue

            slug_base = slugify(parsed["sku"])[:280]
            slug = slug_base
            cnt = 0
            while Product.objects.filter(slug=slug).exclude(sku=parsed["sku"]).exists():
                cnt += 1
                slug = f"{slug_base}-{cnt}"[:280]

            defaults = {
                "name": parsed["name"],
                "slug": slug,
                "category": cat,
                "price": parsed["price"],
                "cost_price": Decimal("0"),
                "stock": 0,
                "is_active": True,
                "deleted_at": None,
            }
            if parsed.get("weight") is not None:
                defaults["weight"] = parsed["weight"]
            if parsed.get("length") is not None:
                defaults["length"] = parsed["length"]
            if parsed.get("material"):
                defaults["material"] = parsed["material"]
            if parsed.get("euro_norm"):
                defaults["euro_norm"] = parsed["euro_norm"]
            if parsed.get("ficha_tecnica"):
                defaults["ficha_tecnica"] = parsed["ficha_tecnica"]

            prod, created_flag = Product.objects.update_or_create(
                sku=parsed["sku"],
                defaults=defaults,
            )
            if created_flag:
                created += 1
            else:
                updated += 1
            prod.refresh_quality(save=True)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry-run: {len(rows)} filas, {len(rows) - skipped} productos a importar."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Listo: {created} creados, {updated} actualizados, {skipped} omitidos."
                )
            )
