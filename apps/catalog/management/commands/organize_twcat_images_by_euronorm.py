"""
Organiza imágenes TWCAT por norma Euro detectada en el nombre del archivo.

- Extrae SKU normalizado del nombre (TWCAT002_200 → TWCAT002-200).
- Detecta norma Euro (euro2/3/4/5) en el nombre.
- Asigna Product.euro_norm y copia imágenes a media/products/<SKU>/.

Política estricta: si un mismo SKU tiene imágenes con normas distintas → conflict, no aplica.

Uso:
  python manage.py organize_twcat_images_by_euronorm --zip imagenes.zip
  python manage.py organize_twcat_images_by_euronorm --zip imagenes.zip --apply
  python manage.py organize_twcat_images_by_euronorm --zip imagenes.zip --apply --out twcat_norm_report.csv
"""
import csv
import os
import re
from pathlib import Path

import zipfile
from collections import defaultdict

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.catalog.models import Product, ProductImage
from apps.catalog.utils.sku_normalize import normalize_sku_canonical

# Extensiones de imagen
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Patrones para detectar norma (orden: más específico primero)
EURO_PATTERNS = [
    (re.compile(r"euro\s*5|euro5", re.I), "EURO5"),
    (re.compile(r"euro\s*4|euro4", re.I), "EURO4"),
    (re.compile(r"euro\s*3|euro3", re.I), "EURO3"),
    (re.compile(r"euro\s*2|euro2", re.I), "EURO2"),
]


def normalize_sku(raw: str) -> str:
    """
    Normaliza SKU para comparar DB ↔ carpeta: uppercase, _ ↔ - equivalentes.
    Ej: TWCAT002_200 → TWCAT002-200, 175x4 → 175X4
    NO inventa sufijos (ej. OVALADO). Solo normaliza el input.
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = str(raw).strip().upper()
    s = s.replace("_", "-")
    s = re.sub(r"-+", "-", s).strip("-")
    return s


def norm_key(raw: str) -> str:
    """
    Normalización agresiva para matchear variantes: 10.7→107, 1.75→175.
    Ej: TWCAT052-10.7 → TWCAT052107, 1,75-X-4 → 175X4
    """
    if not raw or not isinstance(raw, str):
        return ""
    s = str(raw).strip().upper()
    s = s.replace(",", ".")
    s = re.sub(r"(\d+)\.(\d{1,2})", r"\1\2", s)
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def pick_best(cands: list) -> "Product | None":
    """
    Cuando hay varios candidatos (duplicados por norm_key), elige el "mejor":
    1) Preferir SKU sin coma (,)
    2) Luego preferir SKU más corto
    3) Luego por id
    """
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    return sorted(
        cands,
        key=lambda p: ("," in (p.sku or ""), len(p.sku or ""), p.id),
    )[0]


def extract_euro_from_path(path_or_name: str) -> str | None:
    """Detecta norma Euro en el path o nombre (euro2/3/4/5)."""
    for pattern, euro in EURO_PATTERNS:
        if pattern.search(path_or_name):
            return euro
    return None


def extract_sku_and_euro_from_path(rel_path: str) -> tuple[str, str | None]:
    """
    Extrae SKU y norma desde ruta relativa.
    REGLA: el SKU SIEMPRE viene de la carpeta (primer segmento), nunca del filename.

    - 2X6EXT/main.png        → (2X6EXT, None)
    - LT040/main.png         → (LT040, None)
    - CLF003/hyundai.png     → (CLF003, None)  ← carpeta es SKU, no "hyundai"
    - TWCAT002_225/file.png  → (TWCAT002-225, None)
    - TWCAT002_250/euro5.png → (TWCAT002-250, EURO5)
    """
    rel_path = rel_path.replace("\\", "/").strip("/")
    parts = rel_path.split("/")
    # Requiere estructura folder/filename; sin carpeta no hay SKU
    if len(parts) < 2:
        return "", None
    folder = parts[0]
    filename = parts[1]

    # Euro se detecta del filename o del path completo (no afecta el SKU)
    euro = extract_euro_from_path(filename)
    if not euro:
        euro = extract_euro_from_path(rel_path)

    sku_norm = normalize_sku(folder)
    return sku_norm, euro


def _product_has_sku_canonico():
    """True si el modelo Product tiene el campo sku_canonico (migración aplicada)."""
    try:
        Product._meta.get_field("sku_canonico")
        return True
    except Exception:
        return False


def _build_products_index():
    """
    Índices de productos por SKU; cada key apunta a LISTAS (hay duplicados).
    - idx_strict: normalize_sku (folder style)
    - idx_aggr: norm_key (agresivo)
    - idx_canonical: sku_canonico / normalize_sku_canonical(sku) para matching zip ↔ DB
    Compatible con servidores donde sku_canonico aún no existe (usa solo normalización de sku).
    """
    idx_strict = defaultdict(list)
    idx_aggr = defaultdict(list)
    idx_canonical = defaultdict(list)
    only_fields = ["id", "sku"]
    if _product_has_sku_canonico():
        only_fields.append("sku_canonico")
    for p in Product.objects.all().only(*only_fields):
        k_strict = normalize_sku(p.sku)
        k_aggr = norm_key(p.sku)
        k_canon = (getattr(p, "sku_canonico", None) or "") or normalize_sku_canonical(p.sku)
        if k_strict:
            idx_strict[k_strict].append(p)
            idx_strict[k_strict.replace("-", "_")].append(p)
        if k_aggr:
            idx_aggr[k_aggr].append(p)
        if k_canon:
            idx_canonical[k_canon].append(p)
    return idx_strict, idx_aggr, idx_canonical


def _load_alias_csv(path: str) -> dict[str, str]:
    """Carga alias zip_sku → db_sku desde CSV (columnas zip_sku, suggested_db_sku o db_sku)."""
    alias = {}
    if not path or not os.path.exists(path):
        return alias
    with open(path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            zip_sku = (row.get("zip_sku") or "").strip()
            db_sku = (row.get("suggested_db_sku") or row.get("db_sku") or "").strip()
            if not zip_sku or not db_sku:
                continue
            alias[zip_sku] = db_sku
            alias[normalize_sku(zip_sku)] = db_sku
            alias[normalize_sku_canonical(zip_sku)] = db_sku
    return alias


class Command(BaseCommand):
    help = (
        "Organiza imágenes TWCAT por norma Euro: extrae SKU y euro del nombre, "
        "asigna euro_norm al producto y copia imágenes a media/products/<SKU>/."
    )

    def add_arguments(self, parser):
        parser.add_argument("--zip", required=True, help="Ruta al ZIP (ej. imagenes.zip)")
        parser.add_argument(
            "--zip-root",
            default="imagenes/",
            help="Carpeta raíz dentro del ZIP (default: imagenes/)",
        )
        parser.add_argument(
            "--out",
            default="twcat_norm_report.csv",
            help="Archivo CSV de salida (default: twcat_norm_report.csv)",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Aplicar cambios: actualizar euro_norm, crear ProductImage, copiar imágenes.",
        )
        parser.add_argument(
            "--alias-csv",
            default="",
            help="CSV de alias aprobados (columnas zip_sku, suggested_db_sku). Ej: twcat_alias_sugeridos.csv.",
        )

    def handle(self, *args, **opts):
        zip_path = opts["zip"]
        zip_root = opts["zip_root"].rstrip("/") + "/"
        out_path = opts["out"]
        apply_changes = opts["apply"]
        alias_csv = (opts.get("alias_csv") or "").strip()

        if not os.path.exists(zip_path):
            self.stderr.write(self.style.ERROR(f"No existe: {zip_path}"))
            return

        media_root = Path(settings.MEDIA_ROOT)
        products_dir = media_root / "products"

        # Índices: strict, aggr, canonical; alias zip_sku → db_sku
        idx_strict, idx_aggr, idx_canonical = _build_products_index()
        alias_map = _load_alias_csv(alias_csv) if alias_csv else {}
        by_sku = {p.sku: p for p in Product.objects.only("id", "sku")} if alias_map else {}

        # Por cada SKU, registrar qué normas vienen en las imágenes (para detectar conflictos)
        sku_euro_sets: dict[str, set[str]] = defaultdict(set)
        rows: list[dict] = []

        with zipfile.ZipFile(zip_path) as zf:
            for name in zf.namelist():
                if not name.startswith(zip_root):
                    continue
                rel = name[len(zip_root) :].lstrip("/")
                if not rel:
                    continue
                ext = os.path.splitext(rel)[1].lower()
                if ext not in IMAGE_EXTENSIONS:
                    continue

                sku_norm, euro = extract_sku_and_euro_from_path(rel)
                if not sku_norm:
                    rows.append({
                        "file": rel,
                        "sku_raw": rel.split("/")[0] if "/" in rel else rel,
                        "sku_norm": "",
                        "euro_detected": euro or "",
                        "product_found": False,
                        "action": "skip_no_sku",
                        "product_id": "",
                        "candidates": "",
                    })
                    continue

                folder_raw = rel.split("/")[0] if "/" in rel else rel
                folder_strict = normalize_sku(folder_raw)
                folder_aggr = norm_key(folder_raw)
                folder_canonical = normalize_sku_canonical(folder_raw)

                cands = []
                db_sku_from_alias = alias_map.get(folder_raw) or alias_map.get(folder_strict) or alias_map.get(folder_canonical)
                if db_sku_from_alias and by_sku:
                    p = by_sku.get(db_sku_from_alias)
                    if p:
                        cands = [p]
                if not cands:
                    cands = idx_strict.get(folder_strict, [])
                if not cands:
                    cands = idx_canonical.get(folder_canonical, [])
                if not cands:
                    cands = idx_aggr.get(folder_aggr, [])

                product = pick_best(cands) if cands else None
                product_found = product is not None

                # Formato candidates para limpieza posterior: "24:1,75-X-4|84:1.75X4"
                candidates_str = "|".join(f"{p.id}:{p.sku}" for p in cands) if len(cands) > 1 else ""

                sku_euro_sets[sku_norm].add(euro) if euro else None

                if not product_found:
                    rows.append({
                        "file": rel,
                        "sku_raw": rel.split("/")[0] if "/" in rel else rel,
                        "sku_norm": sku_norm,
                        "euro_detected": euro or "",
                        "product_found": False,
                        "action": "missing_product",
                        "product_id": "",
                        "candidates": "",
                    })
                    continue

                # Determinar acción: ambiguous_pick cuando hay varios candidatos (reportar para limpieza)
                current_euro = product.euro_norm or ""
                if len(cands) > 1:
                    action = "ambiguous_pick"
                elif euro:
                    if current_euro and current_euro != euro:
                        action = "conflict_euro"
                    elif not current_euro:
                        action = "set_euro"
                    else:
                        action = "ok"
                else:
                    action = "ok"

                # Imagen: asignar position disponible
                existing_positions = set(
                    product.images.values_list("position", flat=True)
                )
                next_pos = 1
                for pos in range(1, ProductImage.MAX_IMAGES_PER_PRODUCT + 1):
                    if pos not in existing_positions:
                        next_pos = pos
                        break
                else:
                    next_pos = 0  # Sin slot

                img_action = "add_image" if next_pos else "skip_full"
                if action == "conflict_euro":
                    img_action = "blocked"

                rows.append({
                    "file": rel,
                    "sku_raw": rel.split("/")[0] if "/" in rel else rel,
                    "sku_norm": sku_norm,
                    "euro_detected": euro or "",
                    "product_found": True,
                    "action": action if action != "ok" else img_action,
                    "product_id": product.id,
                    "candidates": candidates_str,
                })

        # Detectar conflictos: mismo SKU, distintas normas (no setear euro_norm único)
        conflicts = {
            sku: sorted(norms) for sku, norms in sku_euro_sets.items()
            if len(norms) > 1
        }
        if conflicts:
            for sku, norms in conflicts.items():
                available_norms = ", ".join(norms)
                self.stdout.write(
                    self.style.WARNING(f"Conflict SKU {sku}: available_norms=[{available_norms}] -> no se aplicara euro_norm.")
                )
            for r in rows:
                if r["sku_norm"] in conflicts:
                    r["action"] = "conflict_euro"
                    r["available_norms"] = ",".join(conflicts[r["sku_norm"]])

        # Agregar available_norms y candidates a filas sin conflicto
        fieldnames = [
            "file", "sku_raw", "sku_norm", "euro_detected", "product_found",
            "action", "available_norms", "product_id", "candidates",
        ]
        for r in rows:
            if "available_norms" not in r:
                r["available_norms"] = r["euro_detected"] if r.get("euro_detected") else ""
            if "product_id" not in r:
                r["product_id"] = ""
            if "candidates" not in r:
                r["candidates"] = ""

        # Escribir CSV
        with open(out_path, "w", newline="", encoding="utf-8") as fp:
            w = csv.DictWriter(fp, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)

        self.stdout.write(self.style.SUCCESS(f"Reporte: {out_path}"))
        self.stdout.write(f"Total imágenes procesadas: {len(rows)}")
        missing = sum(1 for r in rows if r["action"] == "missing_product")
        conflicts_count = sum(1 for r in rows if r["action"] == "conflict_euro")
        if missing:
            self.stdout.write(self.style.WARNING(f"Producto no encontrado: {missing}"))
        if conflicts_count:
            self.stdout.write(self.style.WARNING(f"Conflictos (normas distintas mismo SKU): {conflicts_count}"))

        if not apply_changes:
            self.stdout.write(
                self.style.NOTICE("Modo dry-run. Usa --apply para aplicar cambios.")
            )
            return

        # === APPLY ===
        products_dir.mkdir(parents=True, exist_ok=True)
        updated_euro = 0
        added_images = 0

        # Agrupar por product_id para asignar posiciones correctamente
        by_product: dict[int, list[dict]] = defaultdict(list)
        for r in rows:
            if r["product_found"] and r["action"] not in ("conflict_euro", "missing_product", "skip_no_sku"):
                pid = r.get("product_id")
                if pid:
                    by_product[pid].append(r)

        with zipfile.ZipFile(zip_path) as zf:
            for product_id, items in by_product.items():
                try:
                    product = Product.objects.get(id=product_id)
                except Product.DoesNotExist:
                    continue
                if any(r["action"] == "conflict_euro" for r in items):
                    continue

                # Actualizar euro_norm si aplica
                euro_to_set = None
                for r in items:
                    if r["euro_detected"] and (not product.euro_norm or product.euro_norm == r["euro_detected"]):
                        euro_to_set = r["euro_detected"]
                        break
                if euro_to_set and (not product.euro_norm or product.euro_norm == euro_to_set):
                    product.euro_norm = euro_to_set
                    product.save(update_fields=["euro_norm"])
                    updated_euro += 1

                # Añadir imágenes (idempotente: usa basename como dest, skip si ya existe)
                # Usar product.sku para path (consistencia con imágenes existentes)
                path_sku = product.sku
                sku_dir = products_dir / path_sku
                sku_dir.mkdir(parents=True, exist_ok=True)
                existing_positions = set(
                    product.images.values_list("position", flat=True)
                )
                existing_image_paths = set(
                    product.images.values_list("image", flat=True)
                )

                for r in items:
                    if r["action"] in ("conflict_euro", "blocked", "skip_full"):
                        continue
                    zip_name = zip_root.rstrip("/") + "/" + r["file"].lstrip("/")
                    try:
                        with zf.open(zip_name) as zf_entry:
                            data = zf_entry.read()
                    except KeyError:
                        continue

                    # Usar basename como dest para idempotencia (mismo source → mismo path)
                    dest_name = os.path.basename(r["file"])
                    rel_path = f"products/{path_sku}/{dest_name}"

                    # Skip si ya existe imagen con mismo path (evitar duplicados en --apply múltiples)
                    if rel_path in existing_image_paths:
                        self.stdout.write(
                            self.style.NOTICE(f"  [skip] {product.sku} ya tiene {dest_name}")
                        )
                        continue

                    next_pos = 1
                    for pos in range(1, ProductImage.MAX_IMAGES_PER_PRODUCT + 1):
                        if pos not in existing_positions:
                            next_pos = pos
                            break
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"  [skip_full] {product.sku} sin slot para {dest_name}")
                        )
                        continue

                    dest_path = sku_dir / dest_name
                    with open(dest_path, "wb") as f:
                        f.write(data)

                    ProductImage.objects.create(
                        product=product,
                        image=rel_path,
                        alt_text=product.name or "",
                        is_primary=(next_pos == 1 and not product.images.exists()),
                        position=next_pos,
                    )
                    existing_positions.add(next_pos)
                    existing_image_paths.add(rel_path)
                    added_images += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  [ok] {product.sku} pos={next_pos} ← {r['file']}"
                        )
                    )

        self.stdout.write(self.style.SUCCESS(f"Listo. euro_norm actualizados: {updated_euro} | Imágenes añadidas: {added_images}"))
