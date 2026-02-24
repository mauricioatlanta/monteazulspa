# Salud técnica SEO – Monteazul SPA

## 1. UnboundLocalError: reverse

**Estado: CORREGIDO**

- **`apps/catalog/views.py`** línea 4: `from django.urls import reverse` (import al inicio del archivo).
- No existe ninguna variable local llamada `reverse` en `product_list`; todas las llamadas usan la función de Django (líneas 245, 256, 697).
- Se eliminó el import redundante que había dentro del `if` (evita confusión y posibles errores).

## 2. UnorderedObjectListWarning en el sitemap

**Estado: CORREGIDO**

En **`config/sitemaps.py`** todos los QuerySets tienen orden fijo:

| Clase               | Orden en `items()`                                      |
|--------------------|----------------------------------------------------------|
| CategorySitemap    | `.order_by("slug")`                                     |
| ProductSitemap     | `.order_by("id")`                                      |
| BlogPostSitemap     | `.order_by("-published_at", "id")`                     |
| VehicleLandingSitemap | `.order_by("brand_id", "model_id", "year_from")` antes de `values_list().distinct()` |

Así la paginación del sitemap es estable y Google no ve orden distinto en cada visita.

## 3. Error 500 en categorías (breadcrumb)

**Estado: CORREGIDO**

- **Causa:** En `templates/catalog/product_list.html` el breadcrumb usaba `current_category.parent.parent` sin comprobar si `current_category.parent` existe. En categorías raíz (`parent is None`) eso lanzaba `AttributeError` y 500.
- **Solución:** La condición se cambió a `{% if current_category.parent and current_category.parent.parent %}` para no acceder a `.parent` sobre `None`.

## Cómo verificar en tu entorno

En el servidor (o local) ejecuta:

```bash
python manage.py check_seo_links --categories
```

Si todo está bien deberías ver solo **OK [200]** y **Errores=0**. Si sigues viendo 500 o UnboundLocalError, asegúrate de tener desplegados los últimos cambios (git pull / redeploy) de:

- `apps/catalog/views.py`
- `config/sitemaps.py`
- `templates/catalog/product_list.html`
