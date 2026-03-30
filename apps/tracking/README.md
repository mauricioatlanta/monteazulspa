# Sistema de Tracking Persistente

Sistema de tracking de eventos de usuario sin depender de Google Analytics. Almacena eventos en base de datos propia para análisis de comportamiento y optimización de conversión.

## 📊 Eventos Capturados

### 1. **whatsapp_click** - Clicks en WhatsApp
- **Payload**: `{ url, text, page }`
- **Uso**: Medir cuántos usuarios hacen clic en el botón de WhatsApp
- **Optimización**: Identificar qué páginas generan más consultas

### 2. **search** - Búsquedas de texto
- **Payload**: `{ query, type, page }`
- **Uso**: Saber qué buscan los usuarios (ej: "2 x 8", "catalítico peugeot")
- **Optimización**: Crear landing pages específicas para búsquedas frecuentes

### 3. **vehicle_search** - Búsqueda por vehículo
- **Payload**: `{ brand, model, year, page }`
- **Uso**: Identificar vehículos más buscados
- **Optimización**: Priorizar stock y SEO para vehículos populares

### 4. **product_click** - Clicks en productos
- **Payload**: `{ url, product_name, sku, page }`
- **Uso**: Medir interés en productos específicos
- **Optimización**: Identificar productos que generan más interés

### 5. **add_to_cart** - Agregar al carrito
- **Payload**: `{ sku, product_name, page }`
- **Uso**: Medir intención de compra
- **Optimización**: Identificar productos con alta conversión

## 🔧 Componentes

### Backend (Django)

**Modelo**: `TrackingEvent`
- `event`: Tipo de evento (CharField con choices)
- `payload`: Datos del evento (JSONField)
- `created_at`: Timestamp automático
- `ip_address`: IP del usuario
- `user_agent`: Navegador/dispositivo

**Endpoint**: `POST /api/tracking/`
- Acepta JSON: `{ "event": "whatsapp_click", "payload": {...} }`
- Validación de tamaño (máx 10KB)
- Rate limiting: 20 eventos por IP cada 5 minutos
- CSRF exempt (API pública)

**Admin**: Panel en `/admin/tracking/trackingevent/`
- Filtros por tipo de evento y fecha
- Búsqueda por IP y payload
- Solo lectura (no se pueden crear manualmente)

### Frontend (JavaScript)

**Archivo**: `static/js/tracking.js`
- Carga automática en todas las páginas (via `base.html`)
- Try/catch en todas las llamadas (no rompe UX si falla)
- Envío asíncrono con `fetch()` + `keepalive`
- Compatible con Google Analytics (dataLayer)

**Función global**: `window.trackEvent(event, payload)`
```javascript
// Uso manual desde cualquier parte del código
trackEvent('custom_event', { 
    action: 'click_banner',
    banner_id: 'promo-2024'
});
```

## 📈 Análisis de Datos

### Consultas SQL útiles

**Top búsquedas de texto**:
```sql
SELECT 
    json_extract(payload, '$.query') as query,
    COUNT(*) as count
FROM tracking_trackingevent
WHERE event = 'search'
GROUP BY query
ORDER BY count DESC
LIMIT 20;
```

**Vehículos más buscados**:
```sql
SELECT 
    json_extract(payload, '$.brand') as brand,
    json_extract(payload, '$.model') as model,
    COUNT(*) as count
FROM tracking_trackingevent
WHERE event = 'vehicle_search'
GROUP BY brand, model
ORDER BY count DESC
LIMIT 20;
```

**Productos más clickeados**:
```sql
SELECT 
    json_extract(payload, '$.sku') as sku,
    json_extract(payload, '$.product_name') as product,
    COUNT(*) as clicks
FROM tracking_trackingevent
WHERE event = 'product_click'
GROUP BY sku
ORDER BY clicks DESC
LIMIT 20;
```

**Tasa de conversión WhatsApp por página**:
```sql
SELECT 
    json_extract(payload, '$.page') as page,
    COUNT(*) as whatsapp_clicks
FROM tracking_trackingevent
WHERE event = 'whatsapp_click'
GROUP BY page
ORDER BY whatsapp_clicks DESC;
```

## 🚀 Instalación

### 1. Aplicar migraciones
```bash
python manage.py migrate tracking
```

### 2. Verificar en admin
- Ir a `/admin/tracking/trackingevent/`
- Debería aparecer vacío inicialmente

### 3. Probar endpoint
```bash
curl -X POST http://localhost:8000/api/tracking/ \
  -H "Content-Type: application/json" \
  -d '{"event":"whatsapp_click","payload":{"test":true}}'
```

Respuesta esperada: `{"status":"ok"}`

### 4. Verificar frontend
- Abrir cualquier página del sitio
- Abrir consola del navegador (F12)
- Hacer clic en un enlace de WhatsApp
- Debería aparecer: `[Tracking] whatsapp_click {...}`

## 🔒 Seguridad

- **Rate limiting**: Máximo 20 eventos del mismo tipo por IP cada 5 minutos
- **Validación de tamaño**: Payload máximo 10KB
- **Sanitización**: Django maneja automáticamente SQL injection
- **CSRF exempt**: Solo para este endpoint (es API pública)
- **No expone errores**: Errores internos devuelven mensaje genérico

## 📊 Métricas Clave a Monitorear

### Semanalmente
1. **Top 10 búsquedas** → Crear contenido/landing pages
2. **Top 10 vehículos** → Priorizar stock
3. **Productos más clickeados** → Destacar en home
4. **Páginas con más clicks WhatsApp** → Replicar estrategia

### Mensualmente
1. **Tendencias de búsqueda** → Identificar estacionalidad
2. **Tasa de conversión por categoría** → Optimizar categorías débiles
3. **Dispositivos más usados** (via user_agent) → Optimizar móvil/desktop

## 🎯 Optimizaciones Futuras

- [ ] Dashboard visual en `/ops/` con gráficos
- [ ] Exportar a CSV/Excel para análisis externo
- [ ] Alertas automáticas (ej: búsqueda sin resultados)
- [ ] A/B testing basado en eventos
- [ ] Heatmaps de clicks
- [ ] Funnel de conversión completo

## 🐛 Troubleshooting

**Eventos no se guardan**:
1. Verificar que la migración está aplicada: `python manage.py showmigrations tracking`
2. Verificar logs del servidor
3. Probar endpoint con curl (ver arriba)

**JavaScript no funciona**:
1. Verificar que `tracking.js` se carga: Ver Network tab en DevTools
2. Verificar consola por errores
3. Activar DEBUG en `tracking.js` (cambiar `const DEBUG = true`)

**Rate limiting muy estricto**:
- Ajustar en `apps/tracking/views.py`: `check_rate_limit(ip_address, event, max_events=50, window_minutes=10)`
