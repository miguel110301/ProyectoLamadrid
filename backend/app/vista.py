"""Datos para la interfaz de administración, con la forma que ya usa el frontend (ids como texto, horas en ms).

Solo lo sirve `GET /api/admin/datos` (exige administrador). El frontend calcula con esto los reportes; las
reglas oficiales viven en `reglas.py` y una prueba compara ambos cálculos para que no se separen.
"""
from zoneinfo import ZoneInfo

from . import operadores
from .reglas import Cfg, a_ts

CAMPOS_CFG = {
    "tolerancia_retardo_min": "toleranciaRetardoMin",
    "limite_entrada_min": "limiteEntradaMin",
    "tolerancia_salida_min": "toleranciaSalidaMin",
    "anticipo_entrada_min": "anticipoEntradaMin",
    "rebote_seg": "reboteSeg",
    "gracia_sin_salida_min": "graciaSinSalidaMin",
}


def nombre_completo(o) -> str:
    return " ".join(p for p in (o["nombres"], o["ap_paterno"], o["ap_materno"]) if p)


def snapshot(con, zona: ZoneInfo, ahora: int) -> dict:
    cfg = Cfg.desde_db(con)
    tz = lambda fecha, hhmm: a_ts(fecha, hhmm, zona)  # noqa: E731
    horarios: dict[int, list] = {}
    for h in con.execute("SELECT * FROM horario ORDER BY vigente_desde, dia_semana, hora_inicio"):
        horarios.setdefault(h["id_operador"], []).append(h)
    bajas: dict[int, list] = {}
    for b in con.execute("SELECT * FROM periodo_baja ORDER BY desde_ts"):
        bajas.setdefault(b["id_operador"], []).append(b)
    con_huella = {f["id_operador"] for f in con.execute("SELECT id_operador FROM huella WHERE id_operador IS NOT NULL")}

    ops = []
    for o in con.execute("SELECT * FROM operador ORDER BY ap_paterno, nombres"):
        versiones: dict[str, list] = {}
        for h in horarios.get(o["id"], []):
            versiones.setdefault(h["vigente_desde"], []).append(
                {"id": h["id"], "dia": h["dia_semana"], "inicio": h["hora_inicio"], "fin": h["hora_fin"]})
        bs = bajas.get(o["id"], [])
        abierta = next((b for b in bs if b["hasta_ts"] is None), None)
        ops.append({
            "id": str(o["id"]), "nombre": nombre_completo(o), "nombres": o["nombres"], "apPaterno": o["ap_paterno"],
            "apMaterno": o["ap_materno"], "nacimiento": o["nacimiento"], "expediente": o["expediente"], "carrera": o["carrera"],
            "huella": o["id"] in con_huella, "activo": bool(o["activo"]), "alta": o["alta_fecha"],
            "bajaMotivo": abierta["motivo"] if abierta else None,
            "diasParaBorrado": operadores.dias_restantes_purga(con, o["id"], ahora),
            "bajas": [{"desde": b["desde_ts"], "hasta": b["hasta_ts"]} for b in bs],
            "versionesHorario": [{"desde": d, "horarios": hs} for d, hs in sorted(versiones.items())],
        })

    fechas_turno = {h["id"]: h for h in con.execute("SELECT * FROM horario")}
    registros = [{
        "id": str(r["id"]), "operadorId": str(r["id_operador"]), "fecha": r["fecha"], "idHorario": r["id_horario"],
        "turno": {"inicio": fechas_turno[r["id_horario"]]["hora_inicio"], "fin": fechas_turno[r["id_horario"]]["hora_fin"]},
        "iniTs": tz(r["fecha"], fechas_turno[r["id_horario"]]["hora_inicio"]),
        "finTs": tz(r["fecha"], fechas_turno[r["id_horario"]]["hora_fin"]),
        "entradaTs": r["entrada_ts"], "salidaTs": r["salida_ts"], "salidaAnticipada": bool(r["salida_anticipada"]),
    } for r in con.execute("SELECT * FROM registro_asistencia ORDER BY entrada_ts")]

    def turno_inicio(x):
        return fechas_turno[x["id_horario"]]["hora_inicio"]

    return {
        "cfg": {js: getattr(cfg, py) for py, js in CAMPOS_CFG.items()},
        "tipos": [{"id": t["id"], "nombre": t["nombre"], "duracion": bool(t["requiere_duracion"])}
                  for t in con.execute("SELECT * FROM tipo_incidencia")],
        "operadores": ops,
        "registros": registros,
        "incidencias": [{
            "id": str(i["id"]), "operadorId": str(i["id_operador"]), "fecha": i["fecha"], "hora": i["hora"],
            "registradoTs": i["registrado_ts"], "programa": i["programa"], "duracionMin": i["duracion_min"],
            "tipo": i["id_tipo"], "observacion": i["observacion"],
        } for i in con.execute("SELECT * FROM incidencia ORDER BY registrado_ts")],
        "justificaciones": [{
            "id": str(j["id"]), "operadorId": str(j["id_operador"]), "fecha": j["fecha"], "idHorario": j["id_horario"],
            "turnoInicio": turno_inicio(j), "motivo": j["motivo"], "creadoTs": j["creado_ts"],
        } for j in con.execute("SELECT * FROM justificacion")],
        "ajustes": [{
            "id": str(a["id"]), "operadorId": str(a["id_operador"]), "fecha": a["fecha"], "idHorario": a["id_horario"],
            "turnoInicio": turno_inicio(a), "estado": a["estado"], "motivo": a["motivo"], "ts": a["creado_ts"],
        } for a in con.execute("SELECT * FROM ajuste_estatus")],
    }
