#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera catalogo_dataset.json desde uno o más archivos CSV.

Uso:
    python generar_json_desde_csv.py archivo1.csv archivo2.csv -o catalogo_dataset.json
    python generar_json_desde_csv.py datos/*.csv -o misc/catalogo_dataset.json

Columnas esperadas (nombres flexibles):
  Categoría, Part#, Descripción / Medidas (In & Cm), Material / Tipo,
  Largo (Mts), Peso Est. (Kg), Precio
"""
import argparse
import csv
import json
from pathlib import Path


COLUMNAS = [
    ("Categoría", ["categoria", "Categoría", "categoria"]),
    ("Part#", ["part_number", "Part#", "part#", "part_number", "codigo", "SKU"]),
    ("Descripción / Medidas (In & Cm)", ["descripcion", "Descripción / Medidas (In & Cm)", "Descripción", "descripcion"]),
    ("Material / Tipo", ["material_tipo", "Material / Tipo", "Material", "material_tipo"]),
    ("Largo (Mts)", ["largo_m", "Largo (Mts)", "largo_mts", "Largo"]),
    ("Peso Est. (Kg)", ["peso_kg", "Peso Est. (Kg)", "peso_est_kg", "Peso"]),
    ("Precio", ["precio", "Precio", "price"]),
]


def _find_column(header, names):
    for i, h in enumerate(header):
        h_clean = (h or "").strip()
        for n in names:
            if h_clean.lower() == n.lower():
                return i
    return None


def parse_csv(path):
    """Devuelve lista de dicts con keys normalizados."""
    productos = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        rows = list(reader)
    if not rows:
        return productos
    header = [str(h).strip() for h in rows[0]]
    indices = {}
    for std_name, aliases in COLUMNAS:
        idx = _find_column(header, aliases)
        if idx is not None:
            indices[std_name] = idx

    for row in rows[1:]:
        if len(row) < 2:
            continue
        item = {}
        for std_name, idx in indices.items():
            if idx < len(row):
                val = row[idx]
                if isinstance(val, str):
                    val = val.strip()
                item[std_name] = val
        if item.get("Part#") or item.get("Categoría"):
            productos.append(item)
    return productos


def main():
    ap = argparse.ArgumentParser(description="Genera JSON de catálogo desde CSVs")
    ap.add_argument("archivos", nargs="+", help="Archivos CSV de entrada")
    ap.add_argument("-o", "--output", default="catalogo_dataset.json", help="Archivo JSON de salida")
    args = ap.parse_args()

    todos = []
    for pat in args.archivos:
        p = Path(pat)
        if p.is_file():
            archivos = [p]
        else:
            archivos = list(Path(".").glob(pat))
        for f in archivos:
            if f.suffix.lower() == ".csv":
                prod = parse_csv(f)
                todos.extend(prod)
                print(f"  {f}: {len(prod)} productos")

    # Normalizar a formato JSON esperado
    salida = []
    for p in todos:
        salida.append({
            "categoria": p.get("Categoría", ""),
            "part_number": p.get("Part#", ""),
            "descripcion": p.get("Descripción / Medidas (In & Cm)", ""),
            "material_tipo": p.get("Material / Tipo", ""),
            "largo_m": _to_num(p.get("Largo (Mts)")),
            "peso_kg": _to_num(p.get("Peso Est. (Kg)")),
            "precio": _to_num(p.get("Precio")) or 0,
        })

    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"productos": salida}, f, ensure_ascii=False, indent=2)

    print(f"\nGenerado: {out_path} ({len(salida)} productos)")
    print(f"Para cargar: python manage.py load_catalogo_dataset {out_path}")


def _to_num(val):
    if val is None or val == "":
        return None
    try:
        s = str(val).replace(",", ".")
        return float(s) if s else None
    except (TypeError, ValueError):
        return None


if __name__ == "__main__":
    main()
