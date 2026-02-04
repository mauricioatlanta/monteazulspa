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

## Comprobar que el servidor sirve /media/

El servidor web (Nginx, Apache, etc.) debe servir la ruta `/media/` desde la carpeta `media/` del proyecto.

Ejemplo para **Nginx**:

```nginx
location /media/ {
    alias /var/www/monteazulspa/media/;
}
```

Si usas solo el servidor de desarrollo (`runserver`), en modo DEBUG Django ya sirve `/media/` automáticamente.
