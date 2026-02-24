# Imágenes por SKU — Estructura y mantenimiento

Estructura estable de imágenes del catálogo: **una carpeta por SKU** bajo `media/products/`.

## Despliegue: comandos no encontrados

Si en el servidor (p. ej. PythonAnywhere o otra copia del repo) ves:

```text
Unknown command: 'audit_media_images'
Unknown command: 'migrate_images_to_sku'
Unknown command: 'dedupe_media'
```

**Causa:** Los archivos nuevos no están en ese entorno. Django solo descubre comandos que existen en el proyecto.

**Qué hacer:**

1. **Si usas Git:** sube los cambios desde tu máquina y en el servidor haz pull:
   ```bash
   git add apps/catalog/utils/ apps/catalog/management/commands/audit_media_images.py apps/catalog/management/commands/migrate_images_to_sku.py apps/catalog/management/commands/dedupe_media.py apps/catalog/models.py apps/catalog/migrations/0006_* docs/IMAGES_BY_SKU.md static/img/ ...
   git commit -m "Imágenes por SKU: upload_to, audit, migrate, dedupe, docs"
   git push
   ```
   En el servidor:
   ```bash
   cd ~/monteazulspa
   git pull
   source venv_monteazul/bin/activate   # o el nombre de tu venv
   python manage.py migrate
   python manage.py audit_media_images --no-hash
   ```

2. **Si no usas Git:** copia manualmente al servidor estos archivos/carpetas:
   - `apps/catalog/utils/` (carpeta completa: `__init__.py`, `media_paths.py`)
   - `apps/catalog/management/commands/audit_media_images.py`
   - `apps/catalog/management/commands/migrate_images_to_sku.py`
   - `apps/catalog/management/commands/dedupe_media.py`
   - `apps/catalog/models.py` (con `upload_to=product_image_upload_to`)
   - `apps/catalog/migrations/0006_product_image_upload_to_by_sku.py`
   - `static/img/placeholder-product.svg`
   - `docs/IMAGES_BY_SKU.md`
   Luego en el servidor: `python manage.py migrate` y ya podrás ejecutar los comandos.

**Comprobar que Django ve los comandos:**

```bash
python manage.py help | grep -E "audit_media|migrate_images|dedupe_media"
```

Deberías ver:

```text
  audit_media_images
  dedupe_media
  migrate_images_to_sku
```

---

## Estructura final

```
media/products/<sku>/
  main.webp      # imagen principal
  01.webp       # imagen adicional 1
  02.webp       # imagen adicional 2
  03.webp       # (opcional)
  banner.webp   # (opcional)
```

**Ejemplo:**

```
media/products/LT043/main.webp
media/products/LT043/01.webp
media/products/LT043/02.webp
```

### Por qué esta estructura

- El **SKU** es el identificador de negocio y no debería cambiar.
- Evita desorden por categorías o cambios de nombre.
- **Drop-in updates**: sustituyes `main.webp` y listo.
- Scripts de backup, limpieza y mantenimiento son sencillos.

---

## Reglas de naming

| Archivo     | Uso                          |
|------------|------------------------------|
| `main.webp`| Imagen principal del producto|
| `01.webp`, `02.webp`, … | Imágenes adicionales (orden) |
| `banner.webp` | Opcional, para banners      |

Las extensiones pueden ser `.webp`, `.png`, `.jpg` según configuración. El `upload_to` dinámico sanitiza nombres y guarda en `products/<sku>/<nombre_sanitizado>`.

---

## Comandos de mantenimiento

### 1. Auditoría (solo reporte)

Revisa todos los `ProductImage`, comprueba si el archivo existe en disco, detecta duplicados por hash y exporta CSV + JSON.

```bash
python manage.py audit_media_images
```

Opciones:

- `--reports-dir=<ruta>` — Directorio de salida (por defecto: `BASE_DIR/reports`)
- `--no-hash` — No calcular duplicados por hash (más rápido)

Salida:

- `reports/audit_media_images.csv`
- `reports/audit_media_images.json`

Campos del reporte: `product_id`, `sku`, `product_name`, `image_id`, `db_path`, `exists`, `found_candidates`, `notes`.

---

### 2. Migración al esquema por SKU

Mueve o copia las imágenes al esquema `products/<sku>/main.webp`, `01.webp`, etc., y actualiza la base de datos.

**Siempre ejecutar primero en modo simulación:**

```bash
python manage.py migrate_images_to_sku
```

Sin `--apply` es **dry-run** (no modifica nada, solo imprime acciones).

**Ejecutar migración manteniendo originales (recomendado la primera vez):**

```bash
python manage.py migrate_images_to_sku --apply --keep-original
```

**Ejecutar migración moviendo (borra origen):**

```bash
python manage.py migrate_images_to_sku --apply
```

**Opciones:**

- `--dry-run` — Solo imprimir (por defecto si no se usa `--apply`)
- `--apply` — Ejecutar cambios en disco y DB
- `--keep-original` — Copiar en lugar de mover; no borra archivos origen
- `--convert-webp` — Convertir a WebP (requiere Pillow)

Si un archivo no existe en la ruta actual, el comando busca por nombre (case-insensitive) en `MEDIA_ROOT`. Si hay un solo candidato, lo usa; si hay varios, lo deja para revisión manual y lo incluye en el reporte.

Reporte final: `reports/migrate_images_to_sku_report.json`.

---

### 3. Deduplicación (limpieza segura)

Calcula el hash de todos los archivos en `media/products/`. Para cada grupo de duplicados:

- **Canonical**: el que esté en `products/<sku>/main.webp` (o `main.<ext>`), si no el path más corto.
- Actualiza las referencias en `ProductImage` para apuntar al canonical.
- Con `--apply`, elimina los archivos duplicados en disco.

**Solo actualizar DB (no borrar archivos):**

```bash
python manage.py dedupe_media
```

**Actualizar DB y eliminar duplicados:**

```bash
python manage.py dedupe_media --apply
```

---

## Flujo recomendado (primera migración)

1. **Auditoría** (solo reporte):
   ```bash
   python manage.py audit_media_images
   ```

2. **Simulación** de migración:
   ```bash
   python manage.py migrate_images_to_sku
   ```

3. **Migración manteniendo originales**:
   ```bash
   python manage.py migrate_images_to_sku --apply --keep-original
   ```

4. Comprobar en el sitio que todas las imágenes se ven bien.

5. **Deduplicar** (opcional):
   ```bash
   python manage.py dedupe_media --apply
   ```

Con `--keep-original` tienes red de seguridad; puedes borrar manualmente los originales cuando confirmes que todo es correcto.

---

## Placeholder en frontend

Si un producto no tiene imagen o la imagen principal no está disponible, las plantillas del catálogo muestran un placeholder estático:

- **Ruta:** `static/img/placeholder-product.svg`
- Puedes sustituir por `placeholder-product.webp` si lo añades en `static/img/` y actualizas las plantillas que usan `{% static 'img/placeholder-product.svg' %}`.

Así se evita `<img src="">` vacío y rotos en listados, detalle, carrito y resultados por vehículo.

---

## Producción en PythonAnywhere

Para que las imágenes se sirvan correctamente en PythonAnywhere:

1. En el **Web** de tu app → **Static files**.
2. Añade una entrada:
   - **URL:** `/media/`
   - **Directory:** `/home/<tu_usuario>/monteazulspa/media`

Sustituye `<tu_usuario>` por tu usuario de PythonAnywhere y `monteazulspa` por la ruta real de tu proyecto si es distinta.

Sin esta configuración, las URLs de `MEDIA_URL` devolverán 404 aunque Django esté bien configurado.

---

## Resumen de archivos tocados

- **Regla de guardado:** `apps/catalog/utils/media_paths.py` (`sanitize_filename`, `product_image_upload_to`) y `ProductImage.image` con `upload_to=product_image_upload_to`.
- **Migración:** `apps/catalog/migrations/0006_product_image_upload_to_by_sku.py`.
- **Comandos:** `audit_media_images`, `migrate_images_to_sku`, `dedupe_media` en `apps/catalog/management/commands/`.
- **Placeholder:** `static/img/placeholder-product.svg` y uso en plantillas del catálogo, carrito y resultados por vehículo.
