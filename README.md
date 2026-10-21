# Control Maestro TvUAQ

Sistema local de registro de asistencia e incidencias para TvUAQ. Corre en una sola PC con Windows 10, sin despliegue automático.

## Estructura

| Carpeta | Contenido |
|---|---|
| `frontend/` | Interfaz (HTML/CSS/JS puro): pantalla operativa `index.html` y administración `admin.html`. Ya conectada a la API: no guarda datos en el navegador. |
| `backend/` | API FastAPI + SQLite: reglas de asistencia, roles (operador, administrador, superusuario), bajas con purga a los 30 días, respaldos con USB, lector de huellas (simulado). `schema.sql` es el esquema. |
| `scripts/` | `demo.sh` (demostración en Mac) e instalación/arranque en Windows (sin probar). |
| `docs/` | `guia-demostracion.md`, `instalacion-windows.md` y muestras de PDF. `docs/cliente/` no se versiona (ver `.gitignore`). |

## Backend (desarrollo)

```sh
cd backend
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest                      # pruebas
.venv/bin/python -m app.crear_admin              # crea el primer administrador (no hay usuario por defecto)
.venv/bin/python -m app.crear_admin --super      # crea el superusuario (cuenta de respaldo del equipo)
.venv/bin/python -m app.respaldar                # respaldo ahora · python -m app.restaurar para restaurar
TVUAQ_SIMULADOR=1 .venv/bin/python -m uvicorn app.main:app_produccion --factory --host 127.0.0.1 --port 8765
```

`TVUAQ_SIMULADOR=1` habilita el lector simulado y `POST /api/dev/huella`. En producción debe ir en `0`.
La base se guarda en `data/tvuaq.db` (ignorada por git). Variables: `TVUAQ_DB`, `TVUAQ_ZONA`, `TVUAQ_SIMULADOR`, `TVUAQ_RESPALDO_LOCAL`, `TVUAQ_RESPALDO_USB`.

## Demostración

```sh
./scripts/demo.sh reiniciar     # base ficticia + lector simulado + modo demostración
```

Pantalla operativa `http://localhost:8765/` · Administración `http://localhost:8765/admin.html` (demo / demo-tvuaq-26).
Guion completo en [docs/guia-demostracion.md](docs/guia-demostracion.md).
