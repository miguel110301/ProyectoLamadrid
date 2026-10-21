# Control Maestro TvUAQ

Sistema local de registro de asistencia e incidencias para TvUAQ. Corre en una sola PC con Windows 10, sin despliegue automático.

## Estructura

| Carpeta | Contenido |
|---|---|
| `frontend/` | Interfaz (HTML/CSS/JS puro): pantalla operativa `index.html` y administración `admin.html`. Hoy sigue siendo el prototipo con datos en localStorage; falta conectarla a la API. |
| `backend/` | API FastAPI + SQLite: reglas de asistencia, roles, bajas con purga a los 30 días, lector de huellas (simulado). `schema.sql` es el esquema. |
| `scripts/` | Instalación y arranque en Windows (sin probar). |
| `docs/` | Documentación (`instalacion-windows.md`) y muestras de PDF. `docs/cliente/` no se versiona (ver `.gitignore`). |

## Backend (desarrollo)

```sh
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                      # pruebas
.venv/bin/python -m app.crear_admin              # crea el primer administrador (no hay usuario por defecto)
TVUAQ_SIMULADOR=1 .venv/bin/python -m uvicorn app.main:app_produccion --factory --host 127.0.0.1 --port 8765
```

`TVUAQ_SIMULADOR=1` habilita el lector simulado y `POST /api/dev/huella`. En producción debe ir en `0`.
La base se guarda en `data/tvuaq.db` (ignorada por git). Variables: `TVUAQ_DB`, `TVUAQ_ZONA`, `TVUAQ_SIMULADOR`.

## Ver solo el prototipo de interfaz

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory frontend
```

Abrir `http://localhost:8765/` (operativa) y `http://localhost:8765/admin.html`. Acceso del prototipo: `admin` / `admin` (solo demostración).
