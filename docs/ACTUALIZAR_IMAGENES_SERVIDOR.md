# Cómo actualizar las imágenes en el servidor

En este proyecto las imágenes de productos están en la carpeta **`media/`** (no se suben con `collectstatic`). Para que las nuevas imágenes aparezcan en el servidor hay que copiar esa carpeta al servidor.

## Opción 1: Sincronizar con rsync (recomendado en Linux/macOS)

Desde tu máquina local, en la raíz del proyecto:

```bash
# Sustituye USUARIO y SERVIDOR por tu usuario y dominio (ej: usuario@monteazulspa.cl)
# y RUTA_PROYECTO por la ruta del proyecto en el servidor (ej: /var/www/monteazulspa)

rsync -avz --delete media/ USUARIO@SERVIDOR:RUTA_PROYECTO/media/
```

- `-a` = modo archivo (permisos, fechas)
- `-v` = verbose
- `-z` = comprimir en la transferencia
- `--delete` = borrar en el servidor los archivos que ya no existan en local (opcional; quítalo si no quieres eliminar nada en el servidor)

Solo productos (sin borrar nada en el servidor):

```bash
rsync -avz media/products/ USUARIO@SERVIDOR:RUTA_PROYECTO/media/products/
```

## Opción 2: Copiar con SCP

```bash
scp -r media/products USUARIO@SERVIDOR:RUTA_PROYECTO/media/
```

## Opción 3: Desde Windows (PowerShell con SCP)

```powershell
scp -r media\products USUARIO@SERVIDOR:RUTA_PROYECTO/media/
```

O usando **rsync** en Windows (WSL o Git Bash):

```bash
rsync -avz media/products/ USUARIO@SERVIDOR:RUTA_PROYECTO/media/products/
```

## Opción 4: Subir por FTP/SFTP

Con FileZilla, WinSCP o similar:

1. Conéctate al servidor por SFTP.
2. Navega a la carpeta del proyecto (ej. `/var/www/monteazulspa`).
3. Sube o sincroniza la carpeta local **`media/`** (o solo **`media/products/`**) a la carpeta **`media/`** del servidor.

## Después de subir los archivos

- **No hace falta** ejecutar `collectstatic`: las imágenes están en `MEDIA_ROOT`, no en `STATIC_ROOT`.
- **Sí hace falta** que la base de datos del servidor tenga los registros de `ProductImage` (ruta en `products/2026/02/04/...`). Si subes código y migraciones y ya ejecutaste `set_product_image` u otro comando que crea esas filas **en la base del servidor** (o si la BD se restaura desde tu copia), las URLs ya apuntarán a los archivos que subiste.
- Si añadiste imágenes solo en local: en el servidor o bien ejecutas los mismos comandos `set_product_image` (y luego subes la carpeta `media/`), o bien copias la BD de desarrollo al servidor (con cuidado en producción).

## Las imágenes no se ven en el servidor (diagnóstico)

Si ya copiaste la carpeta `media/` al servidor pero las imágenes siguen sin verse, el problema suele ser **configuración del servidor web**, no Django.

### 1. Probar una imagen directa

Abre en el navegador una URL de imagen real (la ruta la guarda Django en `ProductImage.image`; suele ser `products/2026/02/04/nombre.png`):

```
https://monteazulspa.cl/media/products/2026/02/04/chevrolet-cruze.png
```

- **Se ve la imagen** → El servidor sí sirve `/media/`; si no se ven en la web, revisa el HTML/template (en este proyecto ya se usa `{{ image.image.url }}`, correcto).
- **404** → Nginx no tiene `location /media/` o la ruta del `alias` es incorrecta.
- **403** → Permisos: Nginx no puede leer la carpeta/archivos.

### 2. Nginx debe servir /media/ (obligatorio en producción)

En producción, **Django no sirve archivos media**; solo lo hace en modo DEBUG. Quien los sirve es Nginx (o Apache).

Configuración correcta para **Nginx**:

```nginx
# Dentro del server { } que atiende monteazulspa.cl

location /media/ {
    alias /var/www/monteazulspa/media/;   # Ruta REAL del proyecto en el servidor
}
```

Errores típicos:

- Usar `root` en vez de `alias` → la ruta final quedaría mal.
- Ruta incorrecta → debe ser exactamente donde está la carpeta `media/` del proyecto.
- Falta la **barra final** en el `alias` → debe ser `.../media/;`.

Si no sabes la ruta del proyecto en el servidor, suele ser algo como `/home/ubuntu/monteazulspa`, `/var/www/monteazulspa` o la que hayas usado al desplegar. Esa misma ruta es la de `MEDIA_ROOT` (en Django es `BASE_DIR / "media"`).

### 3. Que la ruta coincida con Django

En `settings.py`:

- `MEDIA_URL = "/media/"`
- `MEDIA_ROOT = BASE_DIR / "media"`

Por tanto los archivos deben estar en **la carpeta `media/` dentro del proyecto**. Si subiste `media` a otro sitio (ej. `/var/www/media/`), Nginx y Django no coinciden: pon la carpeta dentro del proyecto o ajusta ambos (Django y Nginx) a la misma ruta.

### 4. Permisos en el servidor

Si tienes SSH (o un terminal en el panel):

```bash
# Permisos de lectura para todos (mínimo)
chmod -R 755 /var/www/monteazulspa/media

# Si Nginx corre como www-data (común en Ubuntu):
chown -R www-data:www-data /var/www/monteazulspa/media
```

Sustituye `/var/www/monteazulspa` por la ruta real de tu proyecto.

### 5. Estructura de carpetas de imágenes

En este proyecto las imágenes se guardan con `upload_to="products/%Y/%m/%d/"`, es decir:

- `media/products/2026/02/04/archivo.png`

Al copiar al servidor, mantén esa estructura: **`media/products/2026/02/02/`** y **`media/products/2026/02/04/`** (y las que tengas). No dejes todo en `media/products/` sin las subcarpetas de fecha, o las URLs que guarda la base de datos no encontrarán el archivo.

---

## Resumen: checklist para que se vean las imágenes

1. **Probar URL directa**: `https://monteazulspa.cl/media/products/2026/02/04/chevrolet-cruze.png`
2. **Nginx**: tener `location /media/ { alias RUTA_PROYECTO/media/; }` con la ruta correcta.
3. **Ruta**: la carpeta `media/` en el servidor debe estar dentro del proyecto (misma que `MEDIA_ROOT`).
4. **Estructura**: mantener `media/products/AAAA/MM/DD/` como en local.
5. **Permisos**: `chmod -R 755 media` y, si aplica, `chown -R www-data:www-data media`.

En el repo hay un ejemplo de bloque Nginx: **`docs/nginx-media-ejemplo.conf`**. Solo necesitas que en tu config exista el `location /media/` con la ruta correcta.

Si usas solo el servidor de desarrollo (`runserver`), en modo DEBUG Django ya sirve `/media/` automáticamente.

---

Para **complementar la información de productos** (peso, dimensiones, stock) desde Excel o Google Sheets, ver **`docs/COMPLEMENTAR_DATOS_PRODUCTOS.md`** y el comando `load_product_specs`.
