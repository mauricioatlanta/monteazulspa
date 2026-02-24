# Alias map y SKU canónico (Opción B)

## En el servidor (deploy)

Para que todo funcione en el servidor:

1. **Subir/copiar estos archivos** (si no están):
   - `apps/catalog/models.py` (campo `sku_canonico`)
   - `apps/catalog/utils/sku_normalize.py`
   - `apps/catalog/management/commands/suggest_twcat_aliases.py`
   - `apps/catalog/management/commands/organize_twcat_images_by_euronorm.py`
   - `apps/catalog/migrations/0009_add_sku_canonico.py`
   - `apps/catalog/migrations/0010_backfill_sku_canonico.py`

2. **Migraciones** (para tener el campo `sku_canonico` en la DB):
   ```bash
   python manage.py migrate catalog
   ```

3. **Sin migraciones**: Los comandos son compatibles con una base que aún no tiene `sku_canonico`: se usa solo la normalización del `sku` para el matching. Puedes usar `--alias-csv` y `organize_twcat_images_by_euronorm` sin haber migrado; `suggest_twcat_aliases` también funciona (genera el CSV usando normalización de `sku`).

4. Si **`suggest_twcat_aliases` no aparece** como comando, comprueba que existe el archivo `apps/catalog/management/commands/suggest_twcat_aliases.py` y que la app `catalog` está en `INSTALLED_APPS`.

---

## Resumen

- **`sku_canonico`**: campo en `Product` con SKU normalizado (sin cambiar el SKU visible). Se usa para matching con zip, imágenes y reportes.
- **Alias map**: CSV que mapea nombre de carpeta del zip → SKU en DB. Permite cubrir los "NO MATCH" (ej. TWCAT042_200 → TWCAT042, TWCAT0237_250_SENSOR → TWCAT237-SENSOR).

## Normalización (sku_canonico)

Se aplica automáticamente al guardar producto (si está vacío) y en migración de backfill:

- Mayúsculas, `_` → `-`, doble guión → uno, coma → punto.
- **TWCAT**: ceros a la izquierda eliminados (TWCAT0002--200 → TWCAT2-200).
- **CLF**: O por 0 en bloque numérico (CLFOO2-225 → CLF002-225).

Ejemplos en DB:

| sku (visible)     | sku_canonico  |
|-------------------|---------------|
| TWCAT0002--200    | TWCAT2-200    |
| TWCAT052-10,7     | TWCAT52-10.7  |
| TWCAT042          | TWCAT42       |
| CLFOO2-225        | CLF002-225    |

## Flujo recomendado

### 1. Generar propuestas de alias

```bash
python manage.py suggest_twcat_aliases --zip imagenes.zip --out twcat_alias_sugeridos.csv
```

- **Exact**: carpeta del zip coincide con `sku_canonico` (o normalización) de un producto.
- **Family**: carpeta se mapea por “familia” (ej. TWCAT042_200 → producto TWCAT042).
- **Revisar/crear**: no hay match; puedes editar el CSV y poner en `suggested_db_sku` el SKU de DB correcto (o dejar vacío para no aplicar).

### 2. Ajustar el CSV (opcional)

Para los 7 u otros “NO MATCH”:

- Si un zip_sku debe mapear a un producto concreto, rellena `suggested_db_sku` (y opcionalmente `action=use`).
- Ejemplo: `TWCAT0237_250_SENSOR` → `TWCAT237-SENSOR`.

### 3. Aplicar euro_norm e imágenes con alias

```bash
python manage.py organize_twcat_images_by_euronorm --zip imagenes.zip --alias-csv twcat_alias_sugeridos.csv --apply --out twcat_norm_report.csv
```

- Primero se resuelve carpeta → producto usando el alias CSV (columnas `zip_sku`, `suggested_db_sku`).
- Luego se usa `sku_canonico` para matching cuando no hay alias.
- Con `--apply` se actualiza `euro_norm` y se copian imágenes a `media/products/<sku>/`.

## Comandos útiles

| Comando | Descripción |
|---------|-------------|
| `suggest_twcat_aliases --zip X` | Genera CSV de propuestas (exact + familia). |
| `organize_twcat_images_by_euronorm --zip X` | Reporte en seco (sin aplicar). |
| `organize_twcat_images_by_euronorm --zip X --alias-csv twcat_alias_sugeridos.csv --apply` | Aplica usando alias + sku_canonico. |

## Ver SKUs normalizados (catalíticos TWC)

```bash
python scripts/norm_skus_twc.py
```

O en shell:

```python
from apps.catalog.models import Product, Category
from apps.catalog.utils.sku_normalize import normalize_sku_canonical
root = Category.objects.get(slug="cataliticos-twc")
for p in Product.objects.filter(category=root).values_list("sku", "sku_canonico"):
    print(p[0], "=>", p[1] or normalize_sku_canonical(p[0]))
```
