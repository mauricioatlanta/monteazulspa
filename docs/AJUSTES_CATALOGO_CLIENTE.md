# Ajustes de catálogo — Instrucciones para Cursor

Proyecto: **MonteazulSPA**  
Objetivo: Ajustes de catálogo según observaciones del cliente.

---

## Resumen de lo implementado

| Fase | Acción | Estado |
|------|--------|--------|
| 1 | Euro 3: Verificar productos sin imagen (TWCAT052-10.7, TWCAT052-8) | ✅ Comando |
| 2 | Euro 5: Eliminar productos indicados | ✅ Comando |
| 2 | Euro 5: TWCAT052-16 debe aparecer primero | ✅ Vista product_list |
| 3 | LT043: Reemplazar imagen (5 formas) | ⚠️ Manual |
| 4 | Flexibles: Revisar 12x10, 2x4, 2x10, 3x8 | ✅ Comando |
| 5 | Bloque MTT en ficha técnica de catalíticos | ✅ Template |

---

## Uso del comando

```bash
# Ejecutar todas las fases
python manage.py ajustes_catalogo_cliente

# Solo simular (no modifica)
python manage.py ajustes_catalogo_cliente --dry-run

# Solo una fase
python manage.py ajustes_catalogo_cliente --phase 1   # Euro 3
python manage.py ajustes_catalogo_cliente --phase 2   # Euro 5
python manage.py ajustes_catalogo_cliente --phase 3   # Redondos (LT043)
python manage.py ajustes_catalogo_cliente --phase 4   # Flexibles
```

---

## Acciones manuales requeridas

### Imágenes a reemplazar (el cliente debe proveer los archivos)

1. **TWCAT052-16** — Cambiar imagen principal  
   ```bash
   python manage.py set_product_image TWCAT052-16 --image /ruta/nueva_imagen.png
   ```

2. **TWCAT052 Diesel Ovalado** — Imagen con código corregido  
   ```bash
   python manage.py set_product_image <SKU> --image /ruta/imagen_corregida.png
   ```
   (Reemplazar `<SKU>` por el SKU exacto del producto.)

3. **LT043** — Imagen con dibujo de 5 formas  
   ```bash
   python manage.py set_product_image LT043 --image /ruta/lt043_5formas.png
   ```

---

## Archivos modificados

- `apps/catalog/management/commands/ajustes_catalogo_cliente.py` — Comando nuevo
- `apps/catalog/views.py` — Orden Euro 5 (TWCAT052-16 primero)
- `templates/catalog/product_detail.html` — Bloque MTT
- `apps/catalog/flexibles_nomenclature.py` — Medida 12X10 agregada
