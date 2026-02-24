# HTTPS y dominio canónico (www vs no-www)

> **Primero arregla el certificado:** Ver [ARREGLAR_CERTIFICADO_SSL.md](ARREGLAR_CERTIFICADO_SSL.md).

## Qué hace el proyecto

- **Una sola URL:** Toda visita a `www.monteazulspa.cl` o `http://monteazulspa.cl` se redirige de forma permanente (301) a `https://monteazulspa.cl`. Esto consolida autoridad SEO en una sola versión del dominio.
- **Sitio seguro:** En producción, las cookies de sesión y CSRF se envían solo por HTTPS, y el navegador deja de marcar el sitio como “no seguro”.

Configuración en Django (ya aplicada en `config/settings.py` y `config/middleware.py`):

- **Dominio canónico:** `monteazulspa.cl` (sin www). El subdominio www se redirige a sin www.
- `ALLOWED_HOSTS`: `www.monteazulspa.cl` y `monteazulspa.cl` (más `127.0.0.1`, `localhost` en desarrollo vía `DJANGO_ALLOWED_HOSTS`).
- `CSRF_TRUSTED_ORIGINS`: `https://www.monteazulspa.cl` y `https://monteazulspa.cl`.
- `CANONICAL_HOST = "monteazulspa.cl"` (o variable de entorno `CANONICAL_HOST`).
- `SECURE_PROXY_SSL_HEADER` para que Django confíe en el proxy (nginx) que termina HTTPS.
- **Cuando SSL ya funcione:** `SECURE_SSL_REDIRECT=1` en `.env` (o `True` en settings). Así todo HTTP → HTTPS y todo host → `https://monteazulspa.cl`.
- `SESSION_COOKIE_SECURE` y `CSRF_COOKIE_SECURE` se activan automáticamente cuando `DEBUG=False`.

## Qué debe hacer el servidor (nginx u otro)

1. **Certificado SSL**  
   Tener HTTPS activo (certificado válido, por ejemplo Let's Encrypt). Sin esto, el navegador seguirá mostrando “no seguro” si se accede por HTTP.

2. **Pasar el protocolo a Django**  
   El proxy debe indicar que la petición original era HTTPS. En nginx, en el `location` que hace proxy a Django:

   ```nginx
   proxy_set_header X-Forwarded-Proto $scheme;
   proxy_set_header Host $host;
   ```

   Así Django recibe `X-Forwarded-Proto: https` y marca la petición como segura.

3. **Opcional: redirección en nginx**  
   Puedes redirigir HTTP → HTTPS y/o `www.monteazulspa.cl` → `monteazulspa.cl` en nginx; Django también hace estas redirecciones con el middleware, pero hacerlas en nginx reduce carga en la app.

## Variables de entorno (opcional)

- `CANONICAL_HOST`: host canónico (por defecto `monteazulspa.cl`). Si quisieras usar www, pondrías `CANONICAL_HOST=www.monteazulspa.cl`.
- `DJANGO_DEBUG=False` en producción para que apliquen las redirecciones y cookies seguras.

## Resumen

| Entrada                    | Redirección (301)           |
|----------------------------|-----------------------------|
| `http://monteazulspa.cl`   | → `https://monteazulspa.cl` |
| `http://www.monteazulspa.cl` | → `https://monteazulspa.cl` |
| `https://www.monteazulspa.cl` | → `https://monteazulspa.cl` |
| `https://monteazulspa.cl`  | Sin redirección (canónico) |

Con SSL bien configurado en el servidor y esta configuración, el sitio se verá como seguro y no habrá diferencias entre entrar por `monteazulspa.cl` o `www.monteazulspa.cl`.
