# Complementar datos de productos desde Excel

Para enriquecer el catálogo con **peso**, **dimensiones** (largo, ancho, alto) y **stock** desde hojas Excel o exportaciones de Google Sheets, usa el comando `load_product_specs`.

## Requisito

- `openpyxl`: `pip install openpyxl` (o `pip install -r requirements-catalog.txt`).

## Formato del Excel

El comando detecta automáticamente una fila de cabecera con los nombres de columna (en español o inglés). Ejemplos de cabeceras reconocidas:

| Campo  | Cabeceras aceptadas |
|--------|----------------------|
| Código | Primera columna, o "codigo", "sku", "código", "part#" |
| Peso   | "peso", "weight" |
| Largo  | "largo", "length", "L 19", "l 19" |
| Ancho  | "ancho", "width", "Aπ 10" |
| Alto   | "alto", "height", "Al 16", "al 16" |
| Stock  | "stock", "ESTOCK" |

- **Primera columna**: debe ser el identificador del producto (código o nombre, ej. `twg 10.7 euro 3`, `ET001`).
- Las demás columnas son opcionales; solo se actualizan los campos que tengan valor en el Excel.

Solo se actualizan **productos que ya existan** en el catálogo. La búsqueda se hace por:

1. SKU exacto (sin distinguir mayúsculas).
2. SKU normalizado (sin espacios ni guiones).
3. Nombre del producto que contenga el texto del identificador.

## Uso

```bash
# Todas las hojas del archivo
python manage.py load_product_specs "ruta/al/archivo.xlsx"

# Una hoja concreta
python manage.py load_product_specs "ruta/al/archivo.xlsx" --sheet "Hoja1"

# Solo ver qué se actualizaría (no guarda)
python manage.py load_product_specs "ruta/al/archivo.xlsx" --dry-run
```

## Después de importar

- Los campos **peso**, **largo**, **ancho**, **alto** y **stock** quedan guardados en el modelo `Product`.
- Si quieres que las dimensiones se muestren en la ficha del producto, usa en el template `{{ product.length }}`, `{{ product.width }}`, `{{ product.height }}` (por ejemplo en `product_list.html` o la vista de detalle).

## Migración

La primera vez que uses este flujo, aplica la migración que añade los campos de dimensiones:

```bash
python manage.py migrate catalog
```
