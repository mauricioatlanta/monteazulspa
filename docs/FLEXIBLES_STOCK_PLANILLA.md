# Stock de flexibles según planilla CAT

Referencia de **medidas** y **cantidades en stock**. La lista de modelos está alineada con la **lista de precios** (FLEXIBLE PIPE WITH INNER BRAID REFORZADO + flex reforzado with napples). Se actualiza el catálogo con:

```bash
python manage.py update_flexibles_stock
```

## Nomenclatura en catálogo

Los nombres en catálogo siguen la lista de precios: formato `"N X M"` (ej. `1.75 X 6`, `2.5 X 8`). Para actualizar solo nombres (sin tocar precios):

```bash
python manage.py actualizar_nombres_flexibles
```

## Tabla medida → stock

| Medida (SKU) | Stock |
|--------------|-------|
| 1.75X6       | 148   |
| 1.75X8       | 231   |
| 1.75X12      | 0     |
| 2X4          | 99    |
| 2X6          | 0     |
| 2X8          | 306   |
| 2X10         | 540   |
| 2.5X6        | 176   |
| 2.5X8        | 550   |
| 3X6          | 10    |
| 3X8          | 125   |
| 4X6          | 47    |
| 4X8          | 275   |

**Total: 13 medidas** (según lista de precios). La columna "cliente" de la planilla no se importa como producto.

## En el servidor

1. Asegúrate de tener el comando en el código (este repo).
2. Ejecutar en el proyecto con el venv activado:
   - `python manage.py update_flexibles_stock --dry-run` para revisar.
   - `python manage.py update_flexibles_stock` para aplicar.
3. Si faltan medidas en la categoría Flexibles: `python manage.py update_flexibles_stock --create-missing` (crea productos con precio 0).

Si la planilla cambia, editar el diccionario `FLEXIBLES_MEDIDA_STOCK` en  
`apps/catalog/management/commands/update_flexibles_stock.py` y volver a ejecutar.
