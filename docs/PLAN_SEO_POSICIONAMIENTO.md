# Plan de implementación SEO – MonteAzulSPA.cl

Este documento mapea el plan estratégico de posicionamiento con las tareas técnicas concretas del proyecto Django. Sirve como guía de implementación y checklist.

---

## 📊 Estado actual (diagnóstico técnico)

| Componente | Estado | Observaciones |
|------------|--------|---------------|
| Sitemap.xml | ❌ No existe | No hay `django.contrib.sitemaps` ni ruta `/sitemap.xml` |
| robots.txt | ❌ No existe | No hay vista ni archivo estático |
| Schema.org (JSON-LD) productos | ❌ No existe | No hay datos estructurados en `product_detail.html` |
| Meta description dinámica | ⚠️ Parcial | Solo en `home_welcome.html`; productos y categorías sin meta |
| og:meta (Open Graph) | ❌ No existe | Sin tags para compartir en redes |
| URL canónica | ❌ No existe | No se define `<link rel="canonical">` |
| Google Analytics / GTM | ❌ No existe | No hay tracking en templates |
| Breadcrumbs semánticos | ⚠️ Parcial | Sí hay breadcrumbs visuales; falta schema.org BreadcrumbList |
| Canonical host + HTTPS | ✅ Sí | Middleware `CanonicalHostAndSecureMiddleware` ya configurado |

---

## 1️⃣ Indexación y confianza (prioridad crítica)

### 1.1 Google Search Console
- **Tipo:** Manual (fuera del código)
- **Pasos:**
  1. Crear propiedad en [Google Search Console](https://search.google.com/search-console)
  2. Verificar dominio: método HTML tag o DNS (CNAME/TXT)
  3. Si usas tag meta: agregar a `base_public.html` en `{% block extra_head %}` condicional (variable de settings)

### 1.2 Sitemap.xml
- **Tipo:** Código
- **Django:** Usar `django.contrib.sitemaps`
- **Incluir:**
  - Páginas estáticas: home, catálogo, normativas, asistente catalíticos
  - Productos (slug, `lastmod` desde `updated_at` o `created_at`)
  - Categorías si tienen URLs propias
- **Archivos a modificar/crear:**
  - `config/settings.py`: agregar `'django.contrib.sitemaps'` a `INSTALLED_APPS`
  - Crear `apps/core/sitemaps.py` o `config/sitemaps.py` con `StaticViewSitemap` y sitemap de productos
  - `config/urls.py`: rutas `/sitemap.xml` y opcional `sitemap_index.xml`

### 1.3 robots.txt
- **Tipo:** Código
- **Contenido sugerido:**
  ```
  User-agent: *
  Allow: /
  Disallow: /admin/
  Disallow: /ops/
  Disallow: /operaciones/
  Disallow: /carrito/
  Sitemap: https://www.monteazulspa.cl/sitemap.xml
  ```
- **Implementación:** Vista Django que sirve `text/plain` o archivo estático en `/static/robots.txt` con template que inyecte `Sitemap` URL base.

---

## 2️⃣ SEO técnico en productos y categorías (prioridad muy alta)

### 2.1 Meta tags dinámicos
- **product_detail.html:**
  - `{% block title %}`: ya existe ✅
  - Agregar `meta name="description"` (150–160 caracteres): descripción corta del producto (nombre + categoría + atributos clave)
  - `meta property="og:title"`, `og:description`, `og:image`, `og:url`, `og:type`, `og:site_name`
  - `link rel="canonical"` con URL absoluta del producto
- **product_list.html** (catálogo):
  - Meta description por categoría o genérica: "Catálogo de catalíticos, flexibles y silenciadores MonteAzul. Repuestos de escape con envío a todo Chile."
  - Canonical a la URL filtrada (sin parámetros duplicados si aplica)
- **base_public.html:** Bloque `{% block meta_description %}` y `{% block canonical_url %}` para que las páginas hijas los rellenen.

### 2.2 Datos estructurados (Schema.org)
- **Product (product_detail.html):**
  - `@type`: Product
  - `name`, `description`, `image`, `sku`, `brand` (MonteAzul o genérico)
  - `offers`: Precio, moneda CLP, disponibilidad (`InStock` / `OutOfStock`)
  - `aggregateRating` opcional si hay reviews
- **BreadcrumbList:** En product_detail y product_list para mejorar la jerarquía en SERP
- **Organization:** En base o home para el sitio en general

### 2.3 Estructura de categorías
- URLs actuales: `/productos/` (lista) y `/productos/<slug>/` (producto)
- Si existen listados por categoría (ej. `/productos/?categoria=cataliticos`), asegurar:
  - Títulos y meta por categoría
  - Enlaces internos desde home y entre categorías
- Revisar `apps/catalog/views.py` para ver si hay vistas por categoría con slug.

---

## 3️⃣ Google Maps / SEO local (prioridad muy alta)

- **Tipo:** Manual (fuera del código)
- **Pasos:**
  1. Crear/verificar Perfil de Empresa en [Google Business Profile](https://business.google.com)
  2. Completar: dirección, horarios, teléfono, fotos reales
  3. Categorías: "Proveedor de repuestos automotrices", "Tienda de autopartes", etc.
  4. Enlace al sitio: `https://www.monteazulspa.cl`
  5. Botón WhatsApp visible (ya existe en el sitio)
- **Código opcional:** LocalBusiness schema en la home o en footer para reforzar datos estructurados locales.

---

## 4️⃣ Contenido que convierte (prioridad media-alta)

### 4.1 Textos en categorías y productos
- **Código:** No cambia estructura; el contenido se edita en Admin o en templates.
- Asegurar que cada categoría tenga descripción en Admin (campo `description` en `Category` si existe) y que se muestre en listados.
- Productos: el campo `name` ya es rico; considerar campo `meta_description` o `short_description` en `Product` para SEO sin afectar el nombre comercial.

### 4.2 Guías y contenido educativo
- Crear páginas tipo:
  - "Cuándo cambiar un catalítico"
  - "Diferencias entre silenciador y resonador"
- Implementación: vistas + templates estáticos o con poco contenido dinámico, enlazados desde home y fichas de producto.

### 4.3 Enlaces internos
- En product_detail: enlaces a "Más productos en [Categoría]", "Productos relacionados"
- En home: bloques por categoría (catalíticos, flexibles, silenciadores) con enlaces a listados filtrados
- Breadcrumbs ya ayudan; reforzar con enlaces contextuales en descripciones.

---

## 5️⃣ Medición (prioridad estratégica)

### 5.1 Google Analytics 4
- **Tipo:** Código + configuración manual
- Crear propiedad GA4 en [analytics.google.com](https://analytics.google.com)
- Obtener `MEASUREMENT_ID` (ej. `G-XXXXXXXXXX`)
- Incluir script en `base_public.html` (condicional a `DEBUG=False` o variable de settings):
  ```html
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-XXXXXXXXXX"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    gtag('js', new Date());
    gtag('config', 'G-XXXXXXXXXX');
  </script>
  ```
- Variable de settings: `GOOGLE_ANALYTICS_ID` (vacío en desarrollo).

### 5.2 Eventos de conversión
- `view_item` en product_detail
- `add_to_cart` al agregar al carrito
- `begin_checkout` al iniciar checkout
- `purchase` en página de éxito (post-pago)
- Implementar con `gtag('event', ...)` en los puntos correspondientes.

### 5.3 Search Console + GA4
- Vincular Search Console con GA4 para ver qué búsquedas generan tráfico y conversiones.

---

## 📅 Orden sugerido de implementación

| Fase | Tarea | Esfuerzo | Dependencias |
|------|-------|----------|--------------|
| 1 | Sitemap + robots.txt | 0.5 día | Ninguna |
| 2 | Meta description + canonical + og en base y productos | 0.5 día | Ninguna |
| 3 | Schema Product + BreadcrumbList en product_detail | 0.5 día | Ninguna |
| 4 | Google Analytics (base) | 0.25 día | ID de GA4 |
| 5 | Eventos GA (view_item, add_to_cart, purchase) | 0.25 día | Fase 4 |
| 6 | LocalBusiness schema (opcional) | 0.25 día | Ninguna |
| 7 | Meta por categoría en product_list | 0.25 día | Ninguna |

**Total estimado en código:** ~2.5 días.

**Manual (fuera del código):**
- Google Search Console (verificación)
- Google Business Profile (creación/optimización)
- Vincular Search Console con GA4

---

## 🛠 Archivos clave a tocar

| Archivo | Cambios |
|---------|---------|
| `config/settings.py` | `sitemaps`, `GOOGLE_ANALYTICS_ID`, `SITE_URL` |
| `config/urls.py` | sitemap, robots |
| `config/sitemaps.py` (nuevo) | StaticViewSitemap, ProductSitemap |
| `templates/base_public.html` | bloques meta, canonical, analytics |
| `templates/catalog/product_detail.html` | meta, og, schema Product, BreadcrumbList |
| `templates/catalog/product_list.html` | meta, canonical, BreadcrumbList |
| `templates/core/home_public.html` | meta, og (si es la home pública) |
| `config/context_processors.py` | `site_url`, `request` para canonical si se usa |

---

## Resumen

El plan estratégico se traduce en **7 tareas de código** y **3 tareas manuales**. Las más impactantes y rápidas son:

1. **Sitemap + robots** → Google empieza a rastrear todo el sitio
2. **Schema Product** → Posibilidad de rich snippets (precio, stock) en búsquedas
3. **Meta + canonical** → Mejor CTR y menos contenido duplicado
4. **Google Analytics** → Base para medir y mejorar

Una vez implementado, el sitio estará preparado para que Google lo entienda, lo indexe y lo muestre cuando busquen "catalítico universal", "flexible reforzado", etc.
