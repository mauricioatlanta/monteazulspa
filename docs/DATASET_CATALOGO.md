# Formato del Dataset de Catálogo

Documentación del formato estándar para actualizar el catálogo de productos desde JSON o CSV.

---

## Reglas de Formato

### Unidades
- **Medidas**: Siempre incluir pulgadas (`"`) y equivalente en centímetros (cm) en la descripción.
  - Ejemplo: `2" (5.08cm) Offset-Center` o `2" x 4" (5.08 x 10.16cm)`
- **Peso**: Campo `peso_kg` en kilogramos (valor numérico).
- **Largo**: Campo `largo_m` en metros (se convierte internamente a cm para logística).

### Nomenclatura del nombre
```
[CATEGORÍA] [PART#] - [DESCRIPCIÓN/VEHÍCULO]
```

**Ejemplos:**
- `Silenciador LT041 - 2" (5.08cm) Offset-Center`
- `Tipo Original CAT-HY01 - Hyundai Accent / Kia Rio`
- `Flexible FLM204 - 2" x 4" (5.08 x 10.16cm)`

**Tipo Original**: El nombre debe incluir marca y modelo del vehículo para SEO y búsqueda interna.

### Materiales y tipos
Se mapean automáticamente a:
- **ACERO**: Acero Aluminizado, Acero
- **INOX**: Inoxidable SS409, Malla Inox, Acero Inox Pulido, Metálico
- **CERAMICO**: Cerámico Euro 3, Cerámico

### Localización
Todo el contenido en **español técnico automotriz**.

---

## Formato JSON

```json
{
  "productos": [
    {
      "categoria": "Silenciador",
      "part_number": "LT041",
      "descripcion": "2\" (5.08cm) Offset-Center",
      "material_tipo": "Acero Aluminizado",
      "largo_m": 0.48,
      "peso_kg": 4.5,
      "precio": 34000
    }
  ]
}
```

**Campos aceptados** (español o inglés):

| JSON (español) | JSON (inglés) | Obligatorio |
|----------------|---------------|-------------|
| `categoria` | `Categoría` | Sí |
| `part_number` | `Part#` | Sí |
| `descripcion` | `Descripción / Medidas (In & Cm)` | Recomendado |
| `material_tipo` | `Material / Tipo` | Recomendado |
| `largo_m` | `Largo (Mts)` | Recomendado |
| `peso_kg` | `Peso Est. (Kg)` | Recomendado |
| `precio` | `Precio` | Sí |

---

## Formato CSV

Columnas (con o sin encabezado):

```
Categoría,Part#,Descripción / Medidas (In & Cm),Material / Tipo,Largo (Mts),Peso Est. (Kg),Precio
Silenciador,LT041,2" (5.08cm) Offset-Center,Acero Aluminizado,0.48,4.5,34000
```

- Codificación: UTF-8
- Separador: coma (`,`)
- Primera fila: encabezados (se detecta automáticamente)

---

## Categorías soportadas

| Categoría en dataset | Slug en BD |
|---------------------|------------|
| Silenciador, Silenciadores | silenciadores |
| Flexible, Flexibles | flexibles |
| Catalítico CLF, Catalitico CLF | cataliticos-twc (Euro 3) |
| Catalítico TWC, Catalitico TWC | cataliticos-twc (Euro 3/4/5 según descripción) |
| Tipo Original, Catalíticos Tipo Original | cataliticos-ensamble-directo |
| Cola Escape, Colas de Escape | colas-de-escape |
| Resonador, Resonadores | resonadores |

---

## Precio Neto y Precio con IVA

En `config/settings.py`:
- `IVA_PERCENT = 19` (Chile)
- `PRICE_INCLUDES_IVA = True`: el precio en el dataset se considera **con IVA incluido**.

El modelo `Product` ofrece:
- `product.get_precio_con_iva()` — precio mostrado al cliente
- `product.get_precio_neto()` — precio sin IVA (facturación)

---

## Generar JSON desde tus CSVs

Si tienes múltiples archivos CSV con el formato descrito:

1. **Opción manual**: Copia las columnas a un JSON siguiendo `misc/catalogo_dataset_muestra.json`.
2. **Opción script**: Usa Python para leer tus CSVs y generar `catalogo_dataset.json`:
   ```python
   import csv
   import json
   productos = []
   with open("tu_archivo.csv", encoding="utf-8") as f:
       reader = csv.DictReader(f)
       for row in reader:
           productos.append({
               "categoria": row.get("Categoría", ""),
               "part_number": row.get("Part#", ""),
               "descripcion": row.get("Descripción / Medidas (In & Cm)", ""),
               "material_tipo": row.get("Material / Tipo", ""),
               "largo_m": float(row.get("Largo (Mts)", 0) or 0),
               "peso_kg": float(row.get("Peso Est. (Kg)", 0) or 0),
               "precio": int(float(row.get("Precio", 0) or 0)),
           })
   with open("catalogo_dataset.json", "w", encoding="utf-8") as out:
       json.dump({"productos": productos}, out, ensure_ascii=False, indent=2)
   ```
3. Cargar: `python manage.py load_catalogo_dataset catalogo_dataset.json`

---

## Recomendaciones técnicas

1. **Consistencia de materiales**: Destacar LTM/SS para durabilidad y LT para presupuesto.
2. **Tipo Original**: Asociar Part# con año y motor vía `ProductCompatibility` para búsquedas por vehículo.
3. **Flexibles**: Las medidas precisas (diámetro x largo) permiten filtros por dimensiones para mecánicos.
4. **Precios**: Usar `get_precio_neto()` y `get_precio_con_iva()` en reportes y punto de venta.
