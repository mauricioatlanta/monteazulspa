# Pasos en el servidor: ficha técnica y comando Euro 3/4/5

## 1. Error: `no such column: catalog_product.ficha_tecnica`

El modelo `Product` tiene el campo `ficha_tecnica` pero la migración no está aplicada en el servidor.

**Opción A – Subir la migración y aplicar**

1. Asegúrate de que en el servidor exista el archivo:
   - `apps/catalog/migrations/0004_product_ficha_tecnica.py`
2. En el proyecto (donde está `manage.py`):
   ```bash
   python manage.py migrate
   ```

**Opción B – Crear la migración en el servidor**

Si en el servidor no tienes el archivo `0004_product_ficha_tecnica.py` (o la numeración es distinta):

```bash
python manage.py makemigrations catalog
python manage.py migrate
```

Después de aplicar la migración, el comando `set_ficha_twcat052` dejará de dar el error de la columna.

---

## 2. Error: `unrecognized arguments: --productos-euro3=...` / `--productos-euro4=...`

La versión del comando en el servidor es antigua y no incluye `--productos-euro3` ni `--productos-euro4`.

**Solución:** Subir al servidor la versión actual del comando:

- `apps/catalog/management/commands/mover_euro5_a_subcategoria.py`

Después podrás usar:

```bash
# Solo Euro 3
python manage.py mover_euro5_a_subcategoria --productos-euro3=SKU1,SKU2

# Solo Euro 4
python manage.py mover_euro5_a_subcategoria --productos-euro4=SKU1,SKU2

# Solo Euro 5
python manage.py mover_euro5_a_subcategoria --productos-euro5=SKU1,SKU2

# Varios a la vez
python manage.py mover_euro5_a_subcategoria --productos-euro3=A,B --productos-euro4=C,D --productos-euro5=E,F
```

---

## 3. Después de aplicar la migración: TWCAT 052

```bash
# Solo asignar ficha técnica (y datos técnicos)
python manage.py set_ficha_twcat052

# Asignar ficha y cambiar la imagen
python manage.py set_ficha_twcat052 --image /ruta/completa/a/twcat052-euro5.png
```
