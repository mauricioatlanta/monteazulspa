# Arreglar certificado SSL (Let's Encrypt)

## 1. Obtener el certificado

En el servidor (Ubuntu/Debian):

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d monteazulspa.cl -d www.monteazulspa.cl
```

Certbot configurará nginx automáticamente. Los archivos quedarán en:

- `/etc/letsencrypt/live/monteazulspa.cl/fullchain.pem`
- `/etc/letsencrypt/live/monteazulspa.cl/privkey.pem`

## 2. Verificar renovación automática

```bash
sudo certbot renew --dry-run
```

## 3. Activar redirecciones en Django

Cuando el certificado funcione correctamente, en el servidor (o `.env`):

```bash
SECURE_SSL_REDIRECT=1
```

Así Django forzará:

- HTTP → HTTPS (301)
- `monteazulspa.cl` → `https://www.monteazulspa.cl` (301)

Ver `docs/HTTPS_Y_DOMINIO_CANONICO.md` para detalles completos.
