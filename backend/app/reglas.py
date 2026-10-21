"""Reglas de asistencia: port de `frontend/js/core.js` (TV.calc). Es la especificación de negocio.

Cálculo al vuelo desde `horario`: las faltas no se guardan. Todas las horas se comparan en
milisegundos UTC; las fechas y horas de turno se interpretan en la zona horaria configurada.
"""
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MIN = 60_000


@dataclass(frozen=True)
class Cfg:
    tolerancia_retardo_min: int = 5   # entrada después de 5 min => retardo
    limite_entrada_min: int = 10      # después de 10 min es falta (la entrada SÍ se registra)
    tolerancia_salida_min: int = 3    # salida hasta 3 min antes => sin advertencia
    anticipo_entrada_min: int = 60    # se puede registrar entrada desde 60 min antes
    rebote_seg: int = 15              # dos lecturas en menos de 15 s = el mismo toque
    gracia_sin_salida_min: int = 120  # pasado este margen tras el fin del turno, la entrada deja de estar vigente

    @classmethod
    def desde_db(cls, con: sqlite3.Connection) -> "Cfg":
        filas = {f["clave"]: f["valor"] for f in con.execute("SELECT clave, valor FROM configuracion")}
        campos = cls.__dataclass_fields__
        return cls(**{k: int(filas[k]) for k in campos if k in filas})


def a_ts(fecha: str, hhmm: str, zona: ZoneInfo) -> int:
    y, m, d = map(int, fecha.split("-"))
    h, mi = map(int, hhmm.split(":"))
    return int(datetime(y, m, d, h, mi, tzinfo=zona).timestamp() * 1000)


def fecha_de(ts_ms: int, zona: ZoneInfo) -> str:
    return datetime.fromtimestamp(ts_ms / 1000, zona).strftime("%Y-%m-%d")


def dia_semana(fecha: str) -> int:
    """0 = domingo ... 6 = sábado (como JS getDay)."""
    return date.fromisoformat(fecha).isoweekday() % 7


def estado_entrada(entrada_ts: int, ini_ts: int, cfg: Cfg) -> str:
    """'a-tiempo' (hasta 5 min) · 'retardo' (hasta 10 min) · 'falta' (más de 10: se registra, pero como falta)."""
    if entrada_ts > ini_ts + cfg.limite_entrada_min * MIN:
        return "falta"
    return "retardo" if entrada_ts > ini_ts + cfg.tolerancia_retardo_min * MIN else "a-tiempo"


def _periodos_baja(con, id_operador):
    return [(f["desde_ts"], f["hasta_ts"]) for f in con.execute(
        "SELECT desde_ts, hasta_ts FROM periodo_baja WHERE id_operador = ?", (id_operador,))]


def turnos_de(con, id_operador: int, desde: str, hasta: str, zona: ZoneInfo) -> list[dict]:
    """Turnos programados entre dos fechas (inclusivas). Sin turnos antes del alta ni durante una baja."""
    op = con.execute("SELECT alta_fecha FROM operador WHERE id = ?", (id_operador,)).fetchone()
    if op is None:
        return []
    horarios = con.execute("SELECT * FROM horario WHERE id_operador = ?", (id_operador,)).fetchall()
    bajas = _periodos_baja(con, id_operador)
    out = []
    d = date.fromisoformat(desde)
    fin = date.fromisoformat(hasta)
    while d <= fin:
        f = d.isoformat()
        if f >= op["alta_fecha"]:
            for h in horarios:
                if h["dia_semana"] != dia_semana(f) or h["vigente_desde"] > f:
                    continue
                if h["vigente_hasta"] is not None and h["vigente_hasta"] < f:
                    continue
                ini_ts = a_ts(f, h["hora_inicio"], zona)
                if any(b0 <= ini_ts and (b1 is None or ini_ts < b1) for b0, b1 in bajas):
                    continue
                out.append({"fecha": f, "id_horario": h["id"], "inicio": h["hora_inicio"], "fin": h["hora_fin"],
                            "ini_ts": ini_ts, "fin_ts": a_ts(f, h["hora_fin"], zona)})
        d += timedelta(days=1)
    return sorted(out, key=lambda t: t["ini_ts"])


def registro_vigente(con, id_operador: int, ahora: int, cfg: Cfg, zona: ZoneInfo):
    """Entrada sin salida que todavía corresponde a un turno en curso. Devuelve (registro, turno) o None."""
    for r in con.execute("SELECT * FROM registro_asistencia WHERE id_operador = ? AND salida_ts IS NULL", (id_operador,)):
        h = con.execute("SELECT * FROM horario WHERE id = ?", (r["id_horario"],)).fetchone()
        fin_ts = a_ts(r["fecha"], h["hora_fin"], zona)
        if ahora <= fin_ts + cfg.gracia_sin_salida_min * MIN:
            return r, {"ini_ts": a_ts(r["fecha"], h["hora_inicio"], zona), "fin_ts": fin_ts,
                       "inicio": h["hora_inicio"], "fin": h["hora_fin"]}
    return None


def turno_para_entrada(con, id_operador: int, ahora: int, cfg: Cfg, zona: ZoneInfo):
    """Turno al que corresponde una entrada hecha ahora (o None)."""
    hoy = fecha_de(ahora, zona)
    ya = {(r["fecha"], r["id_horario"]) for r in con.execute(
        "SELECT fecha, id_horario FROM registro_asistencia WHERE id_operador = ? AND fecha = ?", (id_operador, hoy))}
    for t in turnos_de(con, id_operador, hoy, hoy, zona):
        if ahora >= t["ini_ts"] - cfg.anticipo_entrada_min * MIN and ahora < t["fin_ts"] and (t["fecha"], t["id_horario"]) not in ya:
            return t
    return None


def resumen(con, id_operador: int, desde: str, hasta: str, ahora: int, cfg: Cfg, zona: ZoneInfo, pendientes=False) -> dict:
    """Resumen de asistencia de un operador en un periodo.

    Horas en turno = salida - entrada. Faltante = max(0, programado - horas en turno). Una falta cuenta su
    turno completo. Un turno justificado deja de contar como falta, retardo, incompleto y tiempo faltante.
    """
    regs = {(r["fecha"], r["id_horario"]): r for r in con.execute(
        "SELECT * FROM registro_asistencia WHERE id_operador = ? AND fecha BETWEEN ? AND ?", (id_operador, desde, hasta))}
    justs = {(j["fecha"], j["id_horario"]): j for j in con.execute(
        "SELECT * FROM justificacion WHERE id_operador = ?", (id_operador,))}
    ajustes = {(a["fecha"], a["id_horario"]): a for a in con.execute(
        "SELECT * FROM ajuste_estatus WHERE id_operador = ?", (id_operador,))}
    res = {"filas": [], "asistencias": 0, "faltas": 0, "retardos": 0, "incompletos": 0,
           "justificadas": 0, "sin_salida": 0, "faltante_min": 0.0}

    for t in turnos_de(con, id_operador, desde, hasta, zona):
        prog = (t["fin_ts"] - t["ini_ts"]) / MIN
        fila = {**t, "programado_min": prog, "entrada_ts": None, "salida_ts": None, "trabajado_min": 0, "faltante_min": 0.0,
                "estado": "", "retardo": False, "falta_tardia": False, "incompleto": False, "justificada": False,
                "motivo": "", "editado": False, "edicion_motivo": ""}
        r = regs.get((t["fecha"], t["id_horario"]))
        completo = False

        if r is None:
            # Sin entrada pasados los minutos límite ya es falta
            if ahora <= t["ini_ts"] + cfg.limite_entrada_min * MIN:
                if not pendientes:
                    continue
                fila["estado"] = "pendiente"
            else:
                fila["estado"] = "falta"
                fila["faltante_min"] = prog
        else:
            fila["entrada_ts"] = r["entrada_ts"]
            llegada = estado_entrada(r["entrada_ts"], t["ini_ts"], cfg)
            fila["retardo"] = llegada == "retardo"
            fila["falta_tardia"] = llegada == "falta"
            if r["salida_ts"] is None:
                if fila["falta_tardia"]:
                    fila["estado"] = "falta"
                elif ahora <= t["fin_ts"] + cfg.gracia_sin_salida_min * MIN:
                    fila["estado"] = "en-curso"
                else:
                    fila["estado"] = "sin-salida"
            else:
                completo = True
                fila["salida_ts"] = r["salida_ts"]
                fila["trabajado_min"] = round((r["salida_ts"] - r["entrada_ts"]) / MIN)
                fila["faltante_min"] = max(0, prog - fila["trabajado_min"])
                fila["incompleto"] = fila["retardo"] and r["salida_ts"] < t["fin_ts"]
                fila["estado"] = ("falta" if fila["falta_tardia"] else "incompleto" if fila["incompleto"]
                                  else "retardo" if fila["retardo"] else "asistencia")

        # El administrador cambió el estatus a mano (Editar): manda sobre lo calculado
        cuenta_asistencia = completo and not fila["falta_tardia"]
        aj = ajustes.get((t["fecha"], t["id_horario"]))
        if aj:
            fila["editado"] = True
            fila["edicion_motivo"] = aj["motivo"]
            fila["estado"] = aj["estado"]
            fila["retardo"] = aj["estado"] == "retardo"
            fila["incompleto"] = False
            fila["falta_tardia"] = False
            fila["faltante_min"] = prog if aj["estado"] == "falta" else 0
            cuenta_asistencia = aj["estado"] != "falta"

        # Solo se justifica una falta, un retardo o un turno incompleto
        j = justs.get((t["fecha"], t["id_horario"]))
        fila["justificable"] = fila["estado"] == "falta" or fila["retardo"] or fila["incompleto"]
        if j and fila["justificable"]:
            fila["justificada"] = True
            fila["motivo"] = j["motivo"]
            fila["faltante_min"] = 0
            res["justificadas"] += 1

        if cuenta_asistencia:
            res["asistencias"] += 1
        if fila["estado"] == "falta" and not fila["justificada"]:
            res["faltas"] += 1
        if fila["estado"] == "sin-salida":
            res["sin_salida"] += 1
        if fila["retardo"] and not fila["justificada"]:
            res["retardos"] += 1
        if fila["incompleto"] and not fila["justificada"]:
            res["incompletos"] += 1
        res["faltante_min"] += fila["faltante_min"]
        res["filas"].append(fila)
    return res
