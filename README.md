# Control Maestro TvUAQ

Sistema local de registro de asistencia e incidencias para TvUAQ. Corre en una sola PC con Windows 10, sin internet y sin despliegue.

## Estructura

| Carpeta | Contenido |
|---|---|
| `frontend/` | Interfaz (HTML/CSS/JS puro): pantalla operativa `index.html` y administración `admin.html`. Hoy es un prototipo con datos en localStorage. |
| `backend/` | (pendiente) API FastAPI + SQLite. |
| `scripts/` | (pendiente) Respaldos, arranque automático e instalación en Windows. |
| `docs/` | Documentación y muestras de PDF. `docs/cliente/` no se versiona (ver `.gitignore`). |

## Ver el prototipo

```sh
python3 -m http.server 8765 --bind 127.0.0.1 --directory frontend
```

Abrir `http://localhost:8765/` (operativa) y `http://localhost:8765/admin.html`. No abrir con doble clic.
Acceso del prototipo: `admin` / `admin` (solo para demostración).
