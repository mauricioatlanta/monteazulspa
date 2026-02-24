# Cómo actualizar el catálogo

Desde la raíz del proyecto (`e:\projecto\monteazulspa`), en una terminal.

---

## 1. Cargar o actualizar productos desde Excel

Para **crear/actualizar productos** desde tu hoja de precios (por categorías):

```bash
# Si el Excel está en la carpeta misc/ del proyecto (recomendado):
python manage.py load_precios_xlsx "misc/lista precios publico.xlsx"

# O con ruta absoluta o relativa donde esté el archivo:
python manage.py load_precios_xlsx "ruta/al/archivo.xlsx"
```

El comando busca también en: directorio actual, `misc/`, raíz del proyecto y en la carpeta del comando (`apps/catalog/management/commands/`) si no encuentra la ruta indicada.

Requisito: `pip install openpyxl` (o `pip install -r requirements-catalog.txt`).

---

## 2. Cargar catálogo desde dataset JSON

Para cargar o actualizar productos desde un archivo JSON con el formato del dataset maestro:

```bash
python manage.py load_catalogo_dataset misc/catalogo_dataset_muestra.json
python manage.py load_catalogo_dataset misc/catalogo_dataset.json --dry-run
```

**Formato del JSON** (campos en español o inglés):

| Campo | Descripción |
|-------|-------------|
| `categoria` / `Categoría` | Silenciador, Flexible, Catalítico CLF, Catalítico TWC, Tipo Original, Cola Escape |
| `part_number` / `Part#` | Código del producto (SKU) |
| `descripcion` | Medidas en pulgadas y cm, o vehículo (ej: Hyundai Accent / Kia Rio) |
| `material_tipo` | Acero Aluminizado, Inoxidable SS409, Cerámico Euro 3, etc. |
| `largo_m` / `Largo (Mts)` | Largo en metros (se convierte a cm internamente) |
| `peso_kg` / `Peso Est. (Kg)` | Peso en kilogramos |
| `precio` | Precio (neto o con IVA según `PRICE_INCLUDES_IVA` en settings) |

**Reglas aplicadas automáticamente:**
- Nomenclatura: `[CATEGORÍA] [PART#] - [DESCRIPCIÓN]`
- Tipo Original: incluye marca/modelo en el nombre para SEO
- Conversión: largo en metros → cm; peso y precio como numéricos

Ver `misc/catalogo_dataset_muestra.json` como plantilla. Para generar el JSON completo desde tus CSVs, usa las mismas columnas.

---

## 3. Solo actualizar precios desde Excel (archivo en tu PC o servidor)

Si los productos ya existen y solo quieres **refrescar precios**:

```bash
python manage.py update_precios_from_xlsx "ruta\lista precios publico.xlsx"
```

---

## 4. Asignar una imagen a un producto

Para **poner o cambiar la imagen** de un producto por SKU:

```bash
python manage.py set_product_image SKU --image "ruta\a\la\imagen.png"
```

Ejemplo:

```bash
python manage.py set_product_image TWCAT052-12 --image "C:\...\assets\...\twcat052.png"
```

Si no pasas `--image`, el comando busca en rutas por defecto (según el comando).

---

## 5. Cargar precios **en el servidor** (producción)

Si ejecutas `load_precios_xlsx` o `update_precios_from_xlsx` **en el servidor**, el archivo `.xlsx` debe estar **en ese servidor** (no en tu PC).

1. **Subir el Excel al servidor** (desde **tu PC**, en una terminal local, no dentro del SSH):

   - Sustituye `SERVIDOR` por el **dominio o IP real** del servidor (ej: `monteazulspa.cl` o `192.168.1.10`).
   - El archivo `lista precios publico.xlsx` debe estar en tu PC en la carpeta desde la que ejecutas.

   ```bash
   scp "lista precios publico.xlsx" atlantareciclajes@SERVIDOR:/home/atlantareciclajes/monteazulspa/
   ```

   **Importante:** Si ya estás conectado por SSH al servidor, no puedes usar `scp` desde ahí. Abre otra terminal **en tu computador** (donde tengas el .xlsx) y ejecuta el `scp` allí.

   Alternativa: subir el archivo por **FTP/SFTP** (FileZilla, WinSCP, o el explorador de archivos remoto de tu IDE) a la carpeta del proyecto en el servidor.

2. **En el servidor**, dentro del proyecto y con el venv activado:

   ```bash
   cd ~/monteazulspa   # o la ruta real del proyecto
   python manage.py load_precios_xlsx "/home/atlantareciclajes/monteazulspa/lista precios publico.xlsx"
   ```

   Si el archivo está en el proyecto en `misc/` (tras subir el repo o el archivo):

   ```bash
   python manage.py load_precios_xlsx "misc/lista precios publico.xlsx"
   ```

   O en el mismo directorio: `python manage.py load_precios_xlsx "lista precios publico.xlsx"`.

   Para comprobar: `ls -la misc/*.xlsx` o `ls -la *.xlsx`.

---

## 6. Actualizar el catálogo en el servidor

Para que los cambios se vean en producción:

1. **Código y base de datos**  
   - Subir cambios del código (git, FTP, etc.).  
   - En el servidor: `python manage.py migrate` si hay migraciones.  
   - Si cargaste productos o precios en local, o bien ejecutas en el servidor los mismos comandos (`load_precios_xlsx`, `update_precios_from_xlsx`, `set_product_image`) o bien restauras/copias la base de datos (con cuidado en producción).

2. **Imágenes (media)**  
   - Las imágenes están en la carpeta `media/`. Hay que **subir esa carpeta** al servidor (no se actualiza con `collectstatic`).  
   - Ver guía detallada: [ACTUALIZAR_IMAGENES_SERVIDOR.md](ACTUALIZAR_IMAGENES_SERVIDOR.md).  
   - Resumen rápido:
     ```bash
     rsync -avz media/products/ USUARIO@SERVIDOR:RUTA_PROYECTO/media/products/
     ```
     o con SCP/FTP la carpeta `media` (o solo `media/products`).

3. **Archivos estáticos (CSS/JS)**  
   - En el servidor: `python manage.py collectstatic` (si usas `STATIC_ROOT` en producción).

---

## 7. Actualizar stock de flexibles (planilla CAT)

Si tienes la planilla **IMPORTACION CATALITICOS NUEVOS MARCA CAT** con medidas en la fila 2 y cantidades en la fila STOCK (fila 3), puedes actualizar el stock de los flexibles en el catálogo sin subir el Excel:

```bash
# Ver qué se actualizaría (sin guardar)
python manage.py update_flexibles_stock --dry-run

# Aplicar actualización de stock
python manage.py update_flexibles_stock

# Crear productos faltantes (medidas que no existan en Flexibles) con precio 0
python manage.py update_flexibles_stock --create-missing
```

Las medidas que reconoce el comando (SKU normalizado → stock) están definidas en el propio comando. Ver también [FLEXIBLES_STOCK_PLANILLA.md](FLEXIBLES_STOCK_PLANILLA.md) para la tabla de referencia.

---

## 8. Estructura Cataliticos (categoría y subcategorías)

**Cataliticos** es la categoría raíz; **Cataliticos TWC**, **Cataliticos CLF** y **Cataliticos Ensamble Directo** son subcategorías. El mismo comando crea también las subcategorías **Euro 3**, **Euro 4** y **Euro 5** bajo Cataliticos TWC:

```bash
python manage.py estructura_categorias_cataliticos
# o primero: python manage.py estructura_categorias_cataliticos --dry-run
```

Si las Euro 3/4/5 desaparecieron, ejecutar de nuevo `estructura_categorias_cataliticos` las vuelve a crear o reactivar.

---

## 9. Renombrar categorías

Para dejar los nombres de categoría como: **Silenciadores**, **Resonantes**, **Cataliticos**, **Cataliticos TWC**, **Cataliticos CLF**, **Cataliticos Ensamble Directo**, **colas de escapes** (solo se cambia el nombre mostrado, no el slug):

```bash
python manage.py renombrar_categorias
# o primero: python manage.py renombrar_categorias --dry-run
```

---

## 10. Precio Neto y Precio con IVA

En `config/settings.py`:
- `IVA_PERCENT = 19` (Chile)
- `PRICE_INCLUDES_IVA = True`: el precio guardado incluye IVA; `get_precio_neto()` lo calcula.

En código o templates:
- `product.get_precio_con_iva()` — precio a mostrar al cliente
- `product.get_precio_neto()` — precio sin IVA (facturación, reportes)

---

## 11. Otros comandos útiles

- **Stock (todos los productos):** `python manage.py add_stock_all_products 500` (suma stock a todos).
- **Stock flexibles (planilla):** `python manage.py update_flexibles_stock` (ver apartado 6).
- **Vehículos (compatibilidad):** `python manage.py load_vehicles_chile`.
- **Traducción de productos:** `python manage.py translate_products_to_spanish [--dry-run]`.

---

## Resumen rápido

| Qué quieres actualizar | Comando / acción |
|------------------------|------------------|
| Productos y precios desde Excel | `load_precios_xlsx "archivo.xlsx"` |
| Productos desde dataset JSON | `load_catalogo_dataset "archivo.json"` |
| Solo precios desde Excel | `update_precios_from_xlsx "archivo.xlsx"` |
| Stock de flexibles (planilla CAT) | `update_flexibles_stock` (opción `--dry-run` / `--create-missing`) |
| Estructura Cataliticos (raíz + subcategorías) | `estructura_categorias_cataliticos` |
| Nombres de categorías | `renombrar_categorias` (Silenciadores, Resonantes, Cataliticos TWC/CLF, etc.) |
| Imagen de un producto | `set_product_image SKU --image ruta.png` |
| Ver cambios en el servidor | Subir código, migrar, subir carpeta `media/` |
