#!/usr/bin/env bash
# Demostración en Mac/Linux: base ficticia + lector simulado + modo demostración (hora ajustable).
#   ./scripts/demo.sh            arranca con la base de demo existente (la crea si no hay)
#   ./scripts/demo.sh reiniciar  borra la base de demo y la vuelve a crear desde cero
# Nunca toca la base real (data/tvuaq.db).
set -euo pipefail
cd "$(dirname "$0")/../backend"
export TVUAQ_DB="$(cd .. && pwd)/data/demo.db" TVUAQ_SIMULADOR=1
PY=.venv/bin/python
[ -x "$PY" ] || { echo "Falta el entorno: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt"; exit 1; }
if [ "${1:-}" = "reiniciar" ]; then "$PY" -m app.demo_datos --reiniciar; else "$PY" -m app.demo_datos; fi
echo
echo "Pantalla operativa:  http://localhost:8765/"
echo "Administración:      http://localhost:8765/admin.html   (demo / demo-tvuaq-26)"
echo
exec "$PY" -m uvicorn app.main:app_produccion --factory --host 127.0.0.1 --port 8765
