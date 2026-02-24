# Build de Tailwind CSS (velocidad en producción)

En producción ya **no** se usa el CDN de Tailwind. Se sirve un archivo CSS estático desde tu servidor para reducir ~300 ms de carga (crítico en 4G lento y para Core Web Vitals).

## Importante: el servidor NO necesita npm

En el servidor (PythonAnywhere, etc.) **no** tienes que ejecutar `npm run build:css`. Esa orden se ejecuta solo en tu **máquina local** (donde sí tengas Node/npm instalado). El archivo generado `static/css/tailwind.css` se sube al repositorio y el servidor solo sirve ese archivo estático.

## Cómo se usa

- El archivo generado está en **`static/css/tailwind.css`** (minificado).
- La plantilla **`base_public.html`** lo enlaza con `{% static 'css/tailwind.css' %}`.
- En PythonAnywhere: tras `collectstatic`, ese archivo se copia a `staticfiles/css/tailwind.css` y se sirve desde tu dominio.

## Regenerar el CSS (solo en tu PC, donde tengas Node)

Solo hace falta si **añades o cambias clases de Tailwind** en los templates. En tu máquina local (Windows, Mac o Linux con Node instalado):

```bash
npm install   # solo la primera vez o si cambias package.json
npm run build:css
git add static/css/tailwind.css
git commit -m "Actualizar Tailwind CSS"
git push
```

En el servidor: `git pull` y recargar la app. **No ejecutes npm en el servidor** (no está instalado ni hace falta).

## Archivos del build

| Archivo | Uso |
|--------|-----|
| `package.json` | Scripts `build:css` y dependencia `tailwindcss` |
| `tailwind.config.js` | Content (templates), tema (brand, outfit) |
| `tailwind.input.css` | Entrada con `@tailwind base/components/utilities` |
| `static/css/tailwind.css` | **Salida** (commiteada; la usa el sitio) |

## Desarrollo

Para iterar rápido al cambiar clases: `npm run build:css:watch` regenera el CSS al guardar.
