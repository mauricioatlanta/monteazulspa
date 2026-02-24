# Por qué no se ven los cambios después de editar archivos

## 1. Estás viendo el sitio en producción (monteazulspa.cl)

Si abres **https://www.monteazulspa.cl/ops/settings/** los cambios que hiciste en tu máquina **no están en el servidor**. Hay que desplegar:

- Subir los archivos al servidor (por ejemplo `git push` y en el servidor `git pull`, o subir por FTP/rsync).
- Reiniciar la aplicación (por ejemplo `sudo systemctl restart gunicorn` o el proceso que use el proyecto).

Solo después de desplegar verás los cambios en la URL pública.

---

## 2. Caché del navegador

El navegador puede estar mostrando una versión antigua de la página.

- **Windows/Linux:** `Ctrl + Shift + R` o `Ctrl + F5` (recarga forzada).
- **Mac:** `Cmd + Shift + R`.
- O abrir la página en **modo incógnito/privado** para probar sin caché.

---

## 3. Probando en local (runserver)

Si ejecutas `python manage.py runserver` y abres **http://127.0.0.1:8000/ops/settings/**:

- Con `DEBUG = True`, Django vuelve a leer los templates en cada petición; los cambios en `.html` deberían verse al recargar.
- Si no se actualizan, haz **recarga forzada** (Ctrl+Shift+R) por si el navegador cacheó la página.

---

## 4. Resumen

| Dónde ves la página | Qué hacer |
|---------------------|-----------|
| **www.monteazulspa.cl** | Desplegar los archivos al servidor y reiniciar la app. |
| **127.0.0.1:8000** (local) | Recarga forzada (Ctrl+Shift+R) o probar en incógnito. |

Los estilos de la barra de navegación están **dentro del template** `templates/ops/base_ops.html` (no son archivos estáticos separados), así que no hace falta ejecutar `collectstatic` para ver esos cambios; solo desplegar el template y, si aplica, refrescar sin caché.
