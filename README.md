# Veterinaria API

API RESTful desarrollada con **Django REST Framework** para gestionar una clínica veterinaria:
dueños, mascotas, veterinarios con sus especialidades y la agenda de citas.

**Asignatura:** Backend · **Evaluación Sumativa 3** · Analista Programador, Sede Punta Arenas

## Modelos y relaciones

| Modelo | Descripción | Relaciones |
|---|---|---|
| `User` / `Perfil` | Usuario de Django + rol (`ADMIN`, `VETERINARIO`, `CLIENTE`) y teléfono | **One-to-One** `Perfil → User` |
| `Especialidad` | Área de un veterinario (cirugía, dermatología…) | **Many-to-Many** con `Perfil` |
| `Mascota` | Animal registrado por un cliente | **One-to-Many** `User → Mascota` |
| `Cita` | Hora agendada para una mascota con un veterinario | **One-to-Many** `Mascota → Cita` y `User(vet) → Cita` |

## Instalación local

```bash
# 1. Entorno virtual
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 2. Dependencias
pip install -r requirements.txt

# 3. Variables de entorno
cp .env.example .env            # Windows: copy .env.example .env
# Generar una SECRET_KEY y pegarla en .env:
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"

# 4. Base de datos
python manage.py makemigrations clinica
python manage.py migrate
python manage.py cargar_datos   # opcional: usuarios y datos de demostración

# 5. Ejecutar
python manage.py runserver
```

Usuarios de demo (clave `Demo12345!`): `admin_demo`, `vet_demo`, `cliente_demo`.

Pruebas automáticas: `python manage.py test`

## Formato de respuestas

Éxito:
```json
{ "ok": true, "status": 200, "datos": { ... } }
```
Error:
```json
{ "ok": false, "status": 400, "errores": { "campo": ["mensaje"] } }
```
Las listas están paginadas (10 por página): `datos` contiene `count`, `next`, `previous` y `results`.

## Autenticación

JWT con SimpleJWT. Enviar el token en cada petición protegida:
`Authorization: Bearer <access_token>`. El access dura 15 min y el refresh 1 día.

```bash
curl -X POST http://localhost:8000/api/v1/auth/registro/ -H "Content-Type: application/json" \
  -d '{"username":"maria","email":"maria@correo.cl","password":"ClaveSegura#2026","password2":"ClaveSegura#2026"}'

curl -X POST http://localhost:8000/api/v1/auth/login/ -H "Content-Type: application/json" \
  -d '{"username":"maria","password":"ClaveSegura#2026"}'
```

## Endpoints (`/api/v1/`)

| Método | Ruta | Descripción | Acceso |
|---|---|---|---|
| GET | `salud/` | Comprueba que la API funciona | Público |
| POST | `auth/registro/` | Registro (siempre rol CLIENTE) | Público |
| POST | `auth/login/` | Obtiene `access` y `refresh` | Público |
| POST | `auth/refresh/` | Renueva el access token | Público |
| POST | `auth/logout/` | Invalida el refresh token | Autenticado |
| GET | `auth/me/` | Perfil del usuario actual | Autenticado |
| GET | `especialidades/` · `especialidades/{id}/` | Listar / detalle | Autenticado |
| POST · PUT · PATCH · DELETE | `especialidades/` · `especialidades/{id}/` | Crear / editar / borrar | Solo ADMIN |
| GET | `veterinarios/` · `veterinarios/{id}/` | Veterinarios y sus especialidades (`?search=`) | Autenticado |
| GET · POST | `mascotas/` | Listar propias / crear | CLIENTE, ADMIN (VET solo lee) |
| GET · PUT · PATCH · DELETE | `mascotas/{id}/` | Detalle, editar, borrar | Dueño o ADMIN |
| GET · POST | `citas/` | Listar (`?estado=PENDIENTE`) / agendar | CLIENTE, ADMIN (VET solo lee) |
| GET · PUT · PATCH | `citas/{id}/` | Detalle / editar | Cliente dueño, VET asignado, ADMIN |
| DELETE | `citas/{id}/` | Eliminar | Solo ADMIN |

### Reglas de negocio
- Un **cliente** solo ve y gestiona sus mascotas y citas; solo puede **cancelar** una cita (no confirmarla).
- Un **veterinario** solo ve sus citas y solo puede cambiar su `estado` (usar `PATCH`).
- Las citas siempre se crean en estado `PENDIENTE`, deben ser a futuro y un veterinario no puede tener dos citas activas a la misma hora.
- El rol nunca se recibe desde el registro; los veterinarios y administradores se crean desde `/admin/`.

### Códigos HTTP usados
`200` OK · `201` creado · `204` eliminado · `400` datos inválidos · `401` sin token o token inválido ·
`403` sin permiso · `404` no encontrado · `429` demasiadas peticiones · `500` error interno (sin detalles internos).

## Medidas de seguridad aplicadas

- Secretos y configuración en `.env` (no se sube al repositorio; se entrega `.env.example`).
- Rate limiting: `ScopedRateThrottle` en login (5/min) y registro (3/min), más límites globales para anónimos y usuarios.
- CORS restringido a orígenes explícitos (`CORS_ALLOWED_ORIGINS`).
- Consultas mediante el ORM (parametrizadas): sin riesgo de inyección SQL.
- Sanitización de textos con `strip_tags` y validación de formato (teléfono, fechas, longitudes).
- Validación de contraseñas con los validadores de Django y access tokens de vida corta con blacklist al hacer logout.
- Control de acceso por rol con permisos personalizados y querysets filtrados por usuario (evita IDOR).
- Encabezados y cookies seguras cuando `DJANGO_DEBUG=False`.

## Despliegue (URL pública)

Variables mínimas en el servicio (Render, Railway, PythonAnywhere, etc.):
`DJANGO_SECRET_KEY`, `DJANGO_DEBUG=False`, `DJANGO_ALLOWED_HOSTS=<tu-dominio>`, `CSRF_TRUSTED_ORIGINS=https://<tu-dominio>`.

- Build: `pip install -r requirements.txt && python manage.py collectstatic --noinput && python manage.py migrate`
- Start: `gunicorn config.wsgi`

Verificar con `https://<tu-dominio>/api/v1/salud/`.
