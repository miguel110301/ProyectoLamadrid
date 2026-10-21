"""El cálculo de reportes del frontend (core.js) debe dar EXACTAMENTE lo mismo que las reglas oficiales (reglas.py)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from app import demo_datos, vista
from app.reglas import Cfg, resumen

from conftest import ZONA, ts

RAIZ = Path(__file__).resolve().parent.parent.parent
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node no está instalado")


def test_core_js_y_reglas_py_dan_lo_mismo(con, admin):
    ahora = ts("2026-10-21", "12:00")
    con.execute("DELETE FROM administrador")   # la demo crea su propio administrador
    demo_datos.poblar(con, ZONA, ahora=ahora)
    adm = con.execute("SELECT id FROM administrador").fetchone()["id"]
    # Casos extra: cambios manuales de estatus, un horario nuevo y una baja con reingreso
    filas = con.execute("SELECT id_operador, id_horario, fecha FROM registro_asistencia ORDER BY id LIMIT 6").fetchall()
    for i, f in enumerate(filas):
        con.execute("INSERT INTO ajuste_estatus (id_operador, id_horario, fecha, estado, motivo, creado_ts, creado_por) VALUES (?,?,?,?,?,?,?)",
                    (f["id_operador"], f["id_horario"], f["fecha"], ("falta", "retardo", "asistencia")[i % 3], "prueba", ahora, adm))
    desde, hasta = "2026-09-20", "2026-10-21"

    datos = vista.snapshot(con, ZONA, ahora)
    esperado = {}
    cfg = Cfg.desde_db(con)
    for o in datos["operadores"]:
        r = resumen(con, int(o["id"]), desde, hasta, ahora, cfg, ZONA)
        esperado[o["id"]] = {k: r[k] for k in ("asistencias", "faltas", "retardos", "incompletos", "justificadas", "sin_salida", "faltante_min")}
        esperado[o["id"]]["estados"] = [f"{f['fecha']} {f['inicio']} {f['estado']}" for f in r["filas"]]

    cuerpo = json.dumps({"core": str(RAIZ / "frontend" / "js" / "core.js"), "datos": datos, "desde": desde, "hasta": hasta, "ahora": ahora})
    out = subprocess.run(["node", str(Path(__file__).parent / "paridad.js")], input=cuerpo, capture_output=True, text=True,
                         env={**os.environ, "TZ": "America/Mexico_City"}, check=True)
    obtenido = json.loads(out.stdout)
    assert obtenido == esperado
    assert sum(v["faltas"] for v in esperado.values()) > 0 and any(v["justificadas"] for v in esperado.values())   # el caso no es trivial
