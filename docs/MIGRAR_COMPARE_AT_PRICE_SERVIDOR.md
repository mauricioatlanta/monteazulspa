# Aplicar migración compare_at_price en el servidor

El error `no such column: catalog_product.compare_at_price` ocurre porque el código nuevo usa el campo `compare_at_price` pero la base de datos del **servidor** aún no tiene esa columna.

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

1. **Subir el código** (si aún no está): en el servidor debe existir el archivo  
   `apps/catalog/migrations/0007_add_compare_at_price.py`  
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

5. **Si sale "Conflicting migrations detected"** (varias hojas en el grafo), crear la fusión y luego migrar:
   ```bash
   python manage.py makemigrations --merge
   python manage.py migrate catalog
   ```
   Si no hay conflicto, solo:
   ```bash
   python manage.py migrate catalog
   ```
   Deberías ver al final algo como: `Applying catalog.0007_add_compare_at_price... OK` o `Applying catalog.0008_merge_... OK`

6. **Reiniciar uWSGI** (o el proceso que sirva Django):
   ```bash
   sudo systemctl restart uwsgi
   # o: touch /ruta/a/tu/wsgi.py
   ```

Después de esto, la home y el resto de vistas que usan `Product` en **www.monteazulspa.cl** deberían funcionar.
