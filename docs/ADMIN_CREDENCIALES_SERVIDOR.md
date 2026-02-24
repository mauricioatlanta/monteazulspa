# Credenciales de admin en el servidor

Si el usuario **admin** con contraseña **CambiarMe123** no es aceptado en el servidor, suele ser porque:

1. El superusuario no se creó en el servidor (solo en tu máquina local), o  
2. La contraseña en el servidor es distinta.

## Solución: crear o restablecer el usuario admin en el servidor

Conectarte al servidor por SSH y, dentro del directorio del proyecto (donde está `manage.py`), ejecutar **una** de estas opciones.

### Opción A: Crear el superusuario si no existe

```bash
cd /ruta/del/proyecto/monteazulspa   # ajusta la ruta real
source venv/bin/activate              # si usas entorno virtual
python manage.py createsuperuser --username admin --email admin@monteazulspa.cl
```

Te pedirá la contraseña dos veces. Usa **CambiarMe123** (o la que quieras).

### Opción B: Cambiar la contraseña del usuario `admin` existente

Si el usuario `admin` ya existe pero no recuerdas la contraseña:

```bash
python manage.py changepassword admin
```

Introduce la nueva contraseña dos veces (por ejemplo **CambiarMe123**).

### Opción C: Fijar usuario y contraseña desde un comando (sin preguntas)

Útil para scripts o si no puedes escribir interactivamente:

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
u, created = User.objects.get_or_create(username='admin', defaults={'email': 'admin@monteazulspa.cl', 'is_staff': True, 'is_superuser': True})
u.set_password('CambiarMe123')
u.is_staff = True
u.is_superuser = True
u.save()
print('OK: usuario admin actualizado.' if not created else 'OK: usuario admin creado.')
"
```

**Importante:** después de usar la Opción C, cambia la contraseña desde el panel de admin o con `changepassword` si el servidor es de producción, para no dejar la contraseña en el historial del shell.

## Comprobar que existe el usuario

```bash
python manage.py shell -c "
from django.contrib.auth import get_user_model
u = get_user_model().objects.filter(username='admin').first()
print('Existe:', u is not None, 'Staff:', getattr(u, 'is_staff', None), 'Super:', getattr(u, 'is_superuser', None))
"
```

## Notas

- El **username** en Django es **case-sensitive**: `admin` y `Admin` son distintos.
- La URL del admin suele ser: `https://www.monteazulspa.cl/admin/`
- Si usas otro usuario (por ejemplo `Admin`), usa ese mismo nombre en `changepassword` o en el script de la Opción C.
