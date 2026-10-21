"""Hace un respaldo ahora, desde la consola (lo usan los scripts de mantenimiento, p. ej. antes de actualizar un driver).

    python -m app.respaldar
"""
import sys
import time
from zoneinfo import ZoneInfo

from . import config, db, respaldos


def main() -> int:
    entorno = config.cargar()
    con = db.conectar(entorno.ruta_db)
    db.iniciar(con)
    resultados = respaldos.respaldar_todo(con, entorno, int(time.time() * 1000), ZoneInfo(entorno.zona_horaria))
    for r in resultados:
        print(f"[{r['destino']}] {'OK' if r['ok'] else 'NO'} · {r['detalle']}" + (f" · {r['archivo']}" if r.get("archivo") else ""))
    return 0 if any(r["ok"] for r in resultados) else 1   # basta con que uno quede bien para poder seguir


if __name__ == "__main__":
    sys.exit(main())
