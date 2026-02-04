# Cómo actualizar el catálogo

Desde la raíz del proyecto (`e:\projecto\monteazulspa`), en una terminal.

---

## 1. Cargar o actualizar productos desde Excel

Para **crear/actualizar productos** desde tu hoja de precios (por categorías):

```bash
python manage.py load_precios_xlsx "ruta\lista precios publico.xlsx"
```

Requisito: `pip install openpyxl` (o `pip install -r requirements-catalog.txt`).

---

## 2. Solo actualizar precios desde Excel

Si los productos ya existen y solo quieres **refrescar precios**:

```bash
python manage.py update_precios_from_xlsx "ruta\lista precios publico.xlsx"
```

---

## 3. Asignar una imagen a un producto

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

## 4. Actualizar el catálogo en el servidor

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

## 5. Otros comandos útiles

- **Stock:** `python manage.py add_stock_all_products 500` (suma stock a todos).
- **Vehículos (compatibilidad):** `python manage.py load_vehicles_chile`.
- **Traducción de productos:** `python manage.py translate_products_to_spanish [--dry-run]`.

---

## Resumen rápido

| Qué quieres actualizar | Comando / acción |
|------------------------|------------------|
| Productos y precios desde Excel | `load_precios_xlsx "archivo.xlsx"` |
| Solo precios desde Excel | `update_precios_from_xlsx "archivo.xlsx"` |
| Imagen de un producto | `set_product_image SKU --image ruta.png` |
| Ver cambios en el servidor | Subir código, migrar, subir carpeta `media/` |
