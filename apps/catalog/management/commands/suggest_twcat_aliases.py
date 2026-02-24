"""
Genera twcat_alias_sugeridos.csv con propuestas de mapeo zip_folder → producto DB.

- Detecta euro por filename dentro de cada carpeta del zip.
- Match exacto por sku_canonico (o normalización de sku).
- Match por familia: TWCAT042_200 → familia TWCAT42 → producto con sku_canonico TWCAT42 (ej. TWCAT042).

Uso:
  python manage.py suggest_twcat_aliases --zip imagenes.zip
  python manage.py suggest_twcat_aliases --zip imagenes.zip --out twcat_alias_sugeridos.csv
"""
import csv
import os
from collections import defaultdict

import zipfile
from django.core.management.base import BaseCommand

from apps.catalog.models import Product
from apps.catalog.utils.sku_normalize import normalize_sku_canonical, sku_family_prefix

# Mismo patrón euro que organize_twcat_images_by_euronorm
EURO_PATTERNS = [
    ("euro5", "EURO5"),
    ("euro4", "EURO4"),
    ("euro3", "EURO3"),
    ("euro2", "EURO2"),
]


def detect_euro_from_path(path: str) -> str | None:
    path_lower = path.lower()
    for token, euro in EURO_PATTERNS:
        if token in path_lower:
            return euro
    return None


def _product_has_sku_canonico():
    try:
        Product._meta.get_field("sku_canonico")
        return True
    except Exception:
        return False


def build_canonical_index():
    """Índice: sku_canonico -> list[Product]; y por familia (prefix) -> list[Product]. Compatible sin campo sku_canonico."""
    by_canonical = defaultdict(list)
    by_family = defaultdict(list)
    only_fields = ["id", "sku"]
    if _product_has_sku_canonico():
        only_fields.append("sku_canonico")
    for p in Product.objects.only(*only_fields).iterator():
        canon = (getattr(p, "sku_canonico", None) or "") or normalize_sku_canonical(p.sku)
        if canon:
            by_canonical[canon].append(p)
        fam = sku_family_prefix(canon or normalize_sku_canonical(p.sku))
        if fam:
            by_family[fam].append(p)
    return by_canonical, by_family


def pick_best_family(candidates):
    """De varios productos de la misma familia, prefiere el "base" (sku_canonico == familia)."""
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    for p in candidates:
        c = (getattr(p, "sku_canonico", None) or "") or normalize_sku_canonical(p.sku)
        if c and sku_family_prefix(c) == c:
            return p
    # Si no hay "base", el de SKU más corto
    return min(candidates, key=lambda p: len(p.sku or ""))


class Command(BaseCommand):
    help = "Sugiere alias zip_folder → producto DB (exact + familia) y escribe CSV para aprobación."

    def add_arguments(self, parser):
        parser.add_argument("--zip", required=True, help="Ruta al ZIP (ej. imagenes.zip)")
        parser.add_argument(
            "--zip-root",
            default="imagenes/",
            help="Carpeta raíz dentro del ZIP (default: imagenes/)",
        )
        parser.add_argument(
            "--out",
            default="twcat_alias_sugeridos.csv",
            help="CSV de salida (default: twcat_alias_sugeridos.csv)",
        )

    def handle(self, *args, **opts):
        zip_path = opts["zip"]
        zip_root = opts["zip_root"].rstrip("/") + "/"
        out_path = opts["out"]

        if not os.path.exists(zip_path):
            self.stderr.write(self.style.ERROR(f"No existe: {zip_path}"))
            return

        by_canonical, by_family = build_canonical_index()

        # Recorrer zip: carpetas únicas y euro por carpeta
        folder_euro = defaultdict(set)
        folder_seen = set()

        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if not name.startswith(zip_root):
                    continue
                rel = name[len(zip_root) :].lstrip("/")
                parts = rel.split("/")
                if len(parts) < 2:
                    continue
                folder = parts[0]
                euro = detect_euro_from_path(rel)
                if euro:
                    folder_euro[folder].add(euro)
                folder_seen.add(folder)

        rows = []
        for zip_sku in sorted(folder_seen):
            euro_detected = ""
            if folder_euro[zip_sku]:
                norms = sorted(folder_euro[zip_sku])
                euro_detected = norms[0] if norms else ""
                if len(norms) > 1:
                    euro_detected = "|".join(norms)

            sku_norm = normalize_sku_canonical(zip_sku)
            product = None
            match_type = ""
            suggested_db_sku = ""
            product_id = ""
            in_db = "N"
            action = "review"

            # 1) Exacto por sku_canonico o normalización
            cands = by_canonical.get(sku_norm, [])
            if cands:
                product = pick_best_family(cands) if len(cands) > 1 else cands[0]
                match_type = "exact"
                suggested_db_sku = product.sku
                product_id = str(product.id)
                in_db = "Y"
                action = "use"

            # 2) Familia: zip TWCAT42-200 → familia TWCAT42 → producto base TWCAT42
            if not product and sku_norm:
                fam = sku_family_prefix(sku_norm)
                if fam:
                    cands = by_family.get(fam, [])
                    if cands:
                        product = pick_best_family(cands)
                        match_type = "family"
                        suggested_db_sku = product.sku
                        product_id = str(product.id)
                        in_db = "Y"
                        action = "use"

            if not product:
                action = "review"
                if sku_norm:
                    # Sugerir crear o mapear manualmente
                    action = "create_or_map"

            rows.append({
                "zip_sku": zip_sku,
                "sku_norm": sku_norm or "",
                "euro_detected": euro_detected,
                "match_type": match_type,
                "suggested_db_sku": suggested_db_sku,
                "product_id": product_id,
                "in_db": in_db,
                "action": action,
            })

        fieldnames = [
            "zip_sku", "sku_norm", "euro_detected", "match_type",
            "suggested_db_sku", "product_id", "in_db", "action",
        ]
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"Salida: {out_path}"))
        exact = sum(1 for r in rows if r["match_type"] == "exact")
        family = sum(1 for r in rows if r["match_type"] == "family")
        review = sum(1 for r in rows if r["action"] in ("review", "create_or_map"))
        self.stdout.write(f"  Exact: {exact} | Family: {family} | Revisar/crear: {review}")
