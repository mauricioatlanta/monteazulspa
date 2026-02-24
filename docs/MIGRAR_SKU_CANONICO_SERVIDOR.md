# Aplicar migración sku_canonico en el servidor

El error `no such column: catalog_product.sku_canonico` ocurre porque el código usa el campo `sku_canonico` pero la base de datos del **servidor** aún no tiene esa columna (las migraciones no se han aplicado allí).

---

## En local (Windows, PowerShell)

Si solo quieres aplicar la migración en tu PC:

```powershell
cd E:\projecto\monteazulspa
python manage.py migrate catalog
```

(Si usas un venv en Windows: `.\venv\Scripts\Activate.ps1` antes.)

---

## En el servidor (Linux) — para arreglar el sitio en vivo

Estos pasos se ejecutan **dentro del servidor** (por SSH), no en tu Windows.

1. **Subir el código** (si aún no está): en el servidor deben existir los archivos  
   `apps/catalog/migrations/0009_add_sku_canonico.py` y  
   `apps/catalog/migrations/0010_backfill_sku_canonico.py`  
   (por ejemplo con `git pull` o tu proceso de deploy).

2. **Conectarte por SSH** al servidor y luego:

3. **Ir al directorio del proyecto** (ruta Linux):
   ```bash
   cd /home/atlantareciclajes/monteazulspa
   ```

4. **Activar el entorno virtual** (Linux):
   ```bash
   source /home/atlantareciclajes/venv_monteazul/bin/activate
   ```

5. **Si hay conflicto de migraciones** (mensaje tipo "Conflicting migrations detected; multiple leaf nodes"):
   ```bash
   python manage.py makemigrations catalog --merge
   ```
   Responde `y` cuando pregunte. Eso crea una migración de fusión (ej. `0012_merge_...`) que une las dos ramas. Luego continúa con el paso 6.

6. **Aplicar migraciones**:
   ```bash
   python manage.py migrate catalog
   ```
   Deberías ver algo como:
   - `Applying catalog.0009_add_sku_canonico... OK`
   - `Applying catalog.0010_backfill_sku_canonico... OK`
   (y si hubo merge, también la nueva migración de fusión; y las posteriores pendientes).

7. **Reiniciar uWSGI** (o el proceso que sirva Django):
   ```bash
   sudo systemctl restart uwsgi
   # o: touch /ruta/a/tu/wsgi.py
   ```

Después de esto, la home (`/`) y el resto de vistas que usan `Product` en **www.monteazulspa.cl** deberían funcionar.
