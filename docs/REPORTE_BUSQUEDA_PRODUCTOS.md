# Reporte: Cómo funciona la búsqueda de productos

## Resumen

En el sitio existen **varios flujos de búsqueda**. La búsqueda **por tipo de vehículo** (marca, modelo, año) depende de la tabla **ProductCompatibility** y de la vista **core** "Buscar por vehículo". Si no hay compatibilidades cargadas para ese vehículo, el resultado será **0 productos**.

---

## 1. Búsqueda por vehículo (marca / modelo / año)

### Dónde está
- **URL:** `/buscar-por-vehiculo/`
- **Nombre de ruta:** `core:vehicle_search`
- **Enlace en header:** "Buscar por vehículo" → apunta aquí.

### Flujo
1. El usuario entra a **Buscar por vehículo** (formulario en `core/home_public.html`).
2. Elige **Año → Marca → Modelo → Motor (opcional)** y envía el formulario (POST a `validate_vehicle`).
3. El backend valida y redirige a la misma URL con GET:  
   `?brand=<id>&model=<id>&year=<año>&engine=<id opcional>`.
4. La vista `vehicle_search` llama a **`_vehicle_results_context(brand_id, model_id, year, engine_id)`** en `apps/core/views.py`.
5. Esa función:
   - Busca en **ProductCompatibility** filas donde:
     - `brand_id`, `model_id` coinciden
     - `year_from <= year <= year_to`
     - `is_active=True`
     - Si se eligió motor: `engine_id` coincide
   - Obtiene los `product_id` de esas filas.
   - Devuelve productos con:
     - `id` en esa lista
     - `is_publishable=True`
     - `is_active=True`
     - `deleted_at` nulo
6. Se renderiza **`templates/core/vehicle_results.html`** con esos productos (o mensaje "No encontramos repuestos compatibles").

### Por qué puede “no funcionar”
- **Falta de datos de compatibilidad:** Si no existen registros en **ProductCompatibility** para la marca/modelo/año (y motor si aplica) elegidos, no hay `product_id` y el resultado es **0 productos**.
- **Productos no publicables:** Aunque exista compatibilidad, si el producto tiene `is_publishable=False`, no se muestra.
- **Compatibilidad inactiva:** Si `ProductCompatibility.is_active=False`, no se considera.

**Conclusión:** La búsqueda por vehículo está construida correctamente a nivel de rutas, vistas y templates, pero **hoy no entrega resultados útiles al usuario** porque la base no tiene compatibilidades activas (en la base real quedó probado: compat activas = 0, compat con producto publicable = 0). En su estado actual, la funcionalidad existe a nivel técnico, pero **no está operativa a nivel comercial/funcional**.

---

## 2. Búsqueda por texto (header y listado de productos)

### Dónde está
- **Formulario del header:** `templates/partials/_header_search.html`  
  - `action` → `catalog:product_list` con `method="get"`, parámetro **`q`**.
- **Vista:** `product_list` y API `product_search_api` en `apps/catalog/views.py`.

### Lógica (`_smart_search_queryset`)
- El parámetro **`q`** se divide en **términos** (por espacios).
- Cada término debe coincidir en **al menos uno** de:
  - `Product.name` (icontains)
  - `Product.sku` (icontains)
  - `Category.name` (icontains)
- Entre términos se exige que **todos** coincidan (AND entre términos, OR entre campos).
- **No se usa** marca, modelo, año ni ProductCompatibility en esta búsqueda.

### Parámetros adicionales en listado
- **`cat`:** slug de categoría (filtra por categoría y subcategorías).
- **`q`:** texto libre (nombre, SKU, categoría).
- En categorías de **catalíticos** se aplican además filtros técnicos (Euro, combustible, diámetro, largo, sensor) y **opcionalmente** `brand_id`, `model_id`, `displacement_cc` vía **`_apply_cataliticos_filters`** (solo cuando estás en una categoría catalítico).

---

## 3. API de búsqueda (autocompletado / uso interno)

### Dónde está
- **URL:** `/productos/api/search/`
- **Nombre:** `catalog:product_search_api`
- **Parámetros:** `q`, `cat`, `enorm`, `combustible`, `diametro`, `largo`, `sensor`, `sort`. Si `cat` es una categoría de catalíticos, también se usan `brand_id`, `model_id`, `displacement_cc` en **`_apply_cataliticos_filters`**.

### Comportamiento
- Misma base que el listado: productos no borrados, orden por categoría y nombre.
- Se aplica filtro por categoría (`cat`), filtros de catalíticos (incl. marca/modelo si se envían) y **`_smart_search_queryset`** con `q`.
- Devuelve JSON con lista de productos (máx. 60) para mostrar en el front.

---

## 4. Asistente de catalíticos (wizard combustible + año + tipo)

### Dónde está
- Parámetros en **product list:** `fuel`, `anno`, `tipo` (twg | clf).
- Vista: `product_list` en `apps/catalog/views.py`.

### Lógica
- **`_wizard_resolve_category_slugs(fuel, anno, tipo)`** convierte:
  - **combustible** (bencina/diesel) + **año** + **tipo** (twg/clf)  
  en **slugs de categoría** (Euro 3/4/5, diesel, CLF/ensamble directo).
- Se filtra por **categoría** (`category__slug__in=wizard_slugs`).
- **No usa** marca/modelo ni ProductCompatibility; es filtro por **norma Euro y tipo de producto**, no por vehículo concreto.

---

## 5. Búsqueda por medidas (escape) — implementada parcialmente y pendiente de validación final de template/enlaces

### Dónde está (confirmado en código)
- **URL:** `/productos/busqueda-escape/`
- **Ruta:** `catalog:escape_search`
- **Vista:** `EscapeSearchView` en `apps/catalog/views_escape_search.py`
- **Lógica:** `apps/catalog/search_escape.py` → `parse_escape_query`, `build_escape_queryset`, `detect_escape_search_type`

### Estado de verificación
La búsqueda por medidas tiene la **ruta y la lógica backend** implementadas (EscapeSearchView, parse_escape_query, build_escape_queryset), pero **debe validarse en servidor** que el template `templates/catalog/escape_search.html` y los enlaces públicos ("Por medidas") existan realmente y estén conectados. Hasta no tener esa comprobación en el entorno objetivo, no se considera cerrada como "completa".

### Cómo funciona de punta a punta
1. El usuario entra a **/productos/busqueda-escape/** (o hace clic en "Por medidas").
2. La implementación esperada contempla un formulario de búsqueda con **placeholder** y **ejemplos clicables**: 2x6, 2.5x8, flexible 2x6, silenciador 2, cola 2.
3. Escribe algo (ej. `2x6`, `flexible 2.5x8`, `cola 2`) y pulsa **Buscar** → GET a la misma URL con `?q=...`.
4. **Backend:**
   - `normalize_search_query(q)`: minúsculas, quita tildes, coma→punto, "pulgadas"/"pulg"→espacio, fracciones 1/2→0.5.
   - `parse_escape_query(q)`: detecta **tipo** (flexible, silenciador, resonador, cola, catalítico), **diámetro** (pulg), **largo** (pulg → mm).
   - `build_escape_queryset(q)`: filtra productos por `category__slug` según tipo, `diametro_entrada`/`diametro_salida`, `largo_mm` (con tolerancia).
5. Se renderiza **escape_search.html** con:
   - **parsed**: tipo, diámetro, largo (para mostrar badges "Interpretación").
   - **results**: hasta 48 productos; **total**: cantidad total.
6. Si no hay resultados: mensaje + enlaces a "Buscar en todo el catálogo" y "Buscar por vehículo".

### Ejemplos que entiende el parser
- **Solo medidas:** `2x6`, `2 x 6`, `2.5x8`, `2,5x8` → diámetro y largo (flexible por defecto si hay largo).
- **Con unidad:** `2 pulgadas`, `2 pulg` → diámetro 2.
- **Tipo + medida:** `flexible 2x6`, `silenciador 2`, `resonador 2.5`, `cola 2` → filtra por categoría y diámetro/largo.
- **Fracciones:** `2 1/2` se normaliza a 2.5.

### Dependencia de datos
- Para que aparezcan resultados por **medidas**, los productos deben tener **diametro_entrada**, **diametro_salida** y (en flexibles) **largo_mm** completos. Si la base no tiene esos campos poblados, la búsqueda por medidas puede devolver 0; el flujo y la página siguen operativos.

---

## Diagrama de flujos

```
Usuario quiere repuestos por vehículo
    → Header "Buscar por vehículo" → /buscar-por-vehiculo/
    → Formulario (año, marca, modelo, motor)
    → POST validar-vehiculo → redirect GET ?brand=&model=&year=
    → vehicle_search → _vehicle_results_context()
    → ProductCompatibility (brand, model, year_from/year_to, engine)
    → Productos con is_publishable=True
    → vehicle_results.html (o "No encontramos repuestos compatibles")

Usuario busca por texto (nombre/SKU)
    → Header search "q" → catalog:product_list?q=...
    → _smart_search_queryset (name, sku, category)
    → No usa vehículo ni ProductCompatibility

Usuario en catálogo → filtro por categoría catalíticos
    → Si se pasan brand_id, model_id en GET
    → _apply_cataliticos_filters() filtra por compatibilidad
    → Solo aplica cuando cat ∈ categorías catalíticos

Usuario busca por medidas de escape (diámetro/largo)
    → "Por medidas" o /productos/busqueda-escape/
    → GET ?q=2x6 | flexible 2x8 | cola 2 | etc.
    → EscapeSearchView → parse_escape_query + build_escape_queryset
    → Filtro por category slug + diametro_entrada/salida + largo_mm
    → escape_search.html (resultados o mensaje vacío + enlaces)
```

---

## Qué revisar si “no funciona” la búsqueda por vehículo

1. **¿Hay registros en ProductCompatibility?**
   - En Django shell:  
     `ProductCompatibility.objects.filter(is_active=True).count()`
   - Si es 0 (o muy bajo), no hay datos para mostrar por vehículo.

2. **¿Los productos compatibles están publicables?**
   - Productos deben tener `is_publishable=True` para aparecer en resultados de vehicle_search.

3. **¿Marcas y modelos tienen datos?**
   - VehicleBrand, VehicleModel y opcionalmente VehicleEngine deben existir y estar usados en ProductCompatibility.

4. **¿El usuario llega a la página correcta?**
   - "Buscar por vehículo" debe llevar a `/buscar-por-vehiculo/`, no al listado de productos sin parámetros de vehículo.

---

## Resumen de archivos clave

| Función | Archivo |
|--------|---------|
| Búsqueda por vehículo (vista + contexto) | `apps/core/views.py` → `vehicle_search`, `_vehicle_results_context` |
| Validación y redirect GET | `apps/core/views.py` → `validate_vehicle` |
| Formulario “Buscar por vehículo” | `templates/core/home_public.html` |
| Resultados por vehículo | `templates/core/vehicle_results.html` |
| Búsqueda por texto (queryset) | `apps/catalog/views.py` → `_smart_search_queryset` |
| Listado y API de productos | `apps/catalog/views.py` → `product_list`, `product_search_api` |
| Filtros catalíticos (marca/modelo en catálogo) | `apps/catalog/views.py` → `_apply_cataliticos_filters` |
| Búsqueda por medidas (escape) | `apps/catalog/views_escape_search.py` → `EscapeSearchView` |
| Parser y queryset escape | `apps/catalog/search_escape.py` → `parse_escape_query`, `build_escape_queryset` |
| Template búsqueda por medidas | `templates/catalog/escape_search.html` (pendiente de validación en servidor) |
| Modelo de compatibilidad | `apps/catalog/models.py` → `ProductCompatibility` |

Si quieres, el siguiente paso puede ser: (1) un comando o script para contar ProductCompatibility por marca/modelo, o (2) proponer cambios para que al elegir vehículo también se ofrezca un enlace al catálogo filtrado por ese vehículo (cuando esté en categoría catalíticos).
