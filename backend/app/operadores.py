"""Operadores: alta, horarios con versiones, baja, reingreso y purga a los 30 días."""
import sqlite3
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from .db import config_int, transaccion
from .reglas import Cfg, MIN, a_ts, fecha_de, resumen, turnos_de
from .seguridad import ErrorNegocio, bitacora

DIA_MS = 24 * 3600_000
MOTIVOS_BAJA = ("renuncia", "despido", "fin-de-contrato", "otro")


def _validar_horarios(horarios: list[dict]) -> None:
    if not horarios:
        raise ErrorNegocio("sin-horario", "Agrega al menos un turno.")
    for h in horarios:
        if not (0 <= int(h["dia_semana"]) <= 6) or h["hora_fin"] <= h["hora_inicio"]:
            raise ErrorNegocio("horario-invalido", "Cada turno necesita un día válido y una hora de fin posterior a la de inicio.")
    por_dia: dict[int, list] = {}
    for h in horarios:
        por_dia.setdefault(int(h["dia_semana"]), []).append(h)
    for turnos in por_dia.values():
        turnos.sort(key=lambda h: h["hora_inicio"])
        for a, b in zip(turnos, turnos[1:]):
            if b["hora_inicio"] < a["hora_fin"]:
                raise ErrorNegocio("turnos-traslapados", "Hay turnos que se traslapan el mismo día.")


def _no_es_propio(con, actor_id: int, id_op: int) -> None:
    """Conflicto de interés: un administrador que también es operador no puede justificarse, editarse ni darse de baja a sí mismo."""
    f = con.execute("SELECT id_operador FROM administrador WHERE id = ?", (actor_id,)).fetchone()
    if f and f["id_operador"] == id_op:
        raise ErrorNegocio("conflicto-de-interes", "No puedes modificar tus propios turnos u horario: pídeselo a otro administrador o al superusuario.", 403)


def alta_operador(con, datos: dict, horarios: list[dict], actor_id: int, ahora: int, zona: ZoneInfo) -> int:
    for campo in ("nombres", "ap_paterno", "nacimiento", "expediente"):
        if not str(datos.get(campo, "")).strip():
            raise ErrorNegocio("datos-incompletos", f"Falta el campo «{campo}».")
    _validar_horarios(horarios)
    hoy = fecha_de(ahora, zona)
    with transaccion(con):
        try:
            cur = con.execute(
                "INSERT INTO operador (nombres, ap_paterno, ap_materno, nacimiento, expediente, carrera, alta_fecha) VALUES (?,?,?,?,?,?,?)",
                (datos["nombres"].strip(), datos["ap_paterno"].strip(), datos.get("ap_materno", "").strip(),
                 datos["nacimiento"], datos["expediente"].strip(), datos.get("carrera", "").strip(), hoy))
        except sqlite3.IntegrityError:
            raise ErrorNegocio("expediente-repetido", "Ya existe un operador con ese expediente.", 409)
        id_op = cur.lastrowid
        for h in horarios:
            con.execute("INSERT INTO horario (id_operador, dia_semana, hora_inicio, hora_fin, vigente_desde) VALUES (?,?,?,?,?)",
                        (id_op, int(h["dia_semana"]), h["hora_inicio"], h["hora_fin"], hoy))
        bitacora(con, ahora, "administrador", actor_id, "alta-operador", "operador", id_op)
    return id_op


def cambiar_horario(con, id_op: int, horarios: list[dict], desde_fecha: str, actor_id: int, ahora: int) -> None:
    """Versiona el horario: cierra el vigente el día anterior y abre el nuevo, para no reescribir faltas pasadas."""
    _no_es_propio(con, actor_id, id_op)
    _validar_horarios(horarios)
    abiertos = con.execute("SELECT * FROM horario WHERE id_operador = ? AND vigente_hasta IS NULL", (id_op,)).fetchall()
    if any(h["vigente_desde"] > desde_fecha for h in abiertos):
        raise ErrorNegocio("fecha-invalida", "La fecha del cambio no puede ser anterior al inicio del horario actual.")
    cierre = (date.fromisoformat(desde_fecha) - timedelta(days=1)).isoformat()
    with transaccion(con):
        # Un cambio hecho el mismo día de otro lo reemplaza, siempre que ese turno aún no tenga registros ni ajustes
        for h in [h for h in abiertos if h["vigente_desde"] == desde_fecha]:
            usado = any(con.execute(f"SELECT 1 FROM {t} WHERE id_horario = ?", (h["id"],)).fetchone()
                        for t in ("registro_asistencia", "justificacion", "ajuste_estatus"))
            if usado:
                raise ErrorNegocio("horario-en-uso", "Ese horario ya tiene asistencias hoy; el cambio puede aplicarse desde mañana.", 409)
            con.execute("DELETE FROM horario WHERE id = ?", (h["id"],))
        abiertos = [h for h in abiertos if h["vigente_desde"] != desde_fecha]
        con.execute("UPDATE horario SET vigente_hasta = ? WHERE id_operador = ? AND vigente_hasta IS NULL", (cierre, id_op))
        for h in horarios:
            con.execute("INSERT INTO horario (id_operador, dia_semana, hora_inicio, hora_fin, vigente_desde) VALUES (?,?,?,?,?)",
                        (id_op, int(h["dia_semana"]), h["hora_inicio"], h["hora_fin"], desde_fecha))
        bitacora(con, ahora, "administrador", actor_id, "cambiar-horario", "operador", id_op, f"desde {desde_fecha}")


def dar_de_baja(con, id_op: int, motivo: str, actor_id: int, ahora: int) -> None:
    """La baja es inmediata (sin fecha futura). Se conserva todo 30 días y luego `purgar` lo borra."""
    _no_es_propio(con, actor_id, id_op)
    if motivo not in MOTIVOS_BAJA:
        raise ErrorNegocio("motivo-invalido", "Elige un motivo de baja válido.")
    op = con.execute("SELECT activo FROM operador WHERE id = ?", (id_op,)).fetchone()
    if op is None:
        raise ErrorNegocio("no-existe", "No existe ese operador.", 404)
    if not op["activo"]:
        raise ErrorNegocio("ya-de-baja", "Ese operador ya está dado de baja.", 409)
    with transaccion(con):
        con.execute("INSERT INTO periodo_baja (id_operador, desde_ts, motivo, baja_por) VALUES (?,?,?,?)", (id_op, ahora, motivo, actor_id))
        con.execute("UPDATE operador SET activo = 0 WHERE id = ?", (id_op,))
        bitacora(con, ahora, "administrador", actor_id, "baja-operador", "operador", id_op, motivo)


def reingresar(con, id_op: int, actor_id: int, ahora: int) -> None:
    """Revierte una baja (error o regreso) mientras no haya pasado la purga."""
    _no_es_propio(con, actor_id, id_op)
    baja = con.execute("SELECT id FROM periodo_baja WHERE id_operador = ? AND hasta_ts IS NULL", (id_op,)).fetchone()
    if baja is None:
        raise ErrorNegocio("no-esta-de-baja", "Ese operador no está dado de baja.", 409)
    with transaccion(con):
        con.execute("UPDATE periodo_baja SET hasta_ts = ? WHERE id = ?", (ahora, baja["id"]))
        con.execute("UPDATE operador SET activo = 1 WHERE id = ?", (id_op,))
        bitacora(con, ahora, "administrador", actor_id, "reingreso-operador", "operador", id_op)


def dias_restantes_purga(con, id_op: int, ahora: int) -> int | None:
    baja = con.execute("SELECT desde_ts FROM periodo_baja WHERE id_operador = ? AND hasta_ts IS NULL", (id_op,)).fetchone()
    if baja is None:
        return None
    limite = baja["desde_ts"] + config_int(con, "dias_purga_baja") * DIA_MS
    return max(0, -(-(limite - ahora) // DIA_MS))


def purgar(con, ahora: int) -> list[int]:
    """Borra TODO de los operadores cuya baja abierta cumple el plazo (30 días): huella, asistencias,
    justificaciones, incidencias, horarios, bitácora de ese operador y la ficha. Irreversible.
    Deja una sola línea en la bitácora con el id (sin datos personales)."""
    limite = ahora - config_int(con, "dias_purga_baja") * DIA_MS
    ids = [f["id_operador"] for f in con.execute(
        "SELECT id_operador FROM periodo_baja WHERE hasta_ts IS NULL AND desde_ts <= ?", (limite,))]
    for id_op in ids:
        with transaccion(con):
            for tabla in ("huella", "registro_asistencia", "justificacion", "ajuste_estatus", "incidencia", "horario", "periodo_baja"):
                con.execute(f"DELETE FROM {tabla} WHERE id_operador = ?", (id_op,))
            con.execute("UPDATE administrador SET id_operador = NULL WHERE id_operador = ?", (id_op,))
            con.execute("DELETE FROM bitacora WHERE entidad = 'operador' AND entidad_id = ?", (id_op,))
            con.execute("DELETE FROM operador WHERE id = ?", (id_op,))
            bitacora(con, ahora, "sistema", None, "purga-operador", "operador", id_op, "datos eliminados")
    return ids


# ---------- Justificar y Editar (solo administrador; el control de rol lo hace la API) ----------

def _fila_turno(con, id_op, fecha, id_horario, ahora, zona):
    cfg = Cfg.desde_db(con)
    for f in resumen(con, id_op, fecha, fecha, ahora, cfg, zona)["filas"]:
        if f["id_horario"] == id_horario:
            return f
    raise ErrorNegocio("turno-inexistente", "Ese turno no existe o aún no es falta.", 404)


def justificar(con, id_op, fecha, id_horario, motivo, actor_id, ahora, zona) -> None:
    _no_es_propio(con, actor_id, id_op)
    if not motivo.strip():
        raise ErrorNegocio("motivo-obligatorio", "Escribe el motivo de la justificación.")
    fila = _fila_turno(con, id_op, fecha, id_horario, ahora, zona)
    if not fila["justificable"]:
        raise ErrorNegocio("no-justificable", "Solo se puede justificar una falta, un retardo o un turno incompleto.", 409)
    with transaccion(con):
        con.execute("INSERT OR REPLACE INTO justificacion (id_operador, id_horario, fecha, motivo, creado_ts, creado_por) VALUES (?,?,?,?,?,?)",
                    (id_op, id_horario, fecha, motivo.strip(), ahora, actor_id))
        bitacora(con, ahora, "administrador", actor_id, "justificar", "operador", id_op, f"{fecha} horario {id_horario}")


def quitar_justificacion(con, id_op, fecha, id_horario, actor_id, ahora) -> None:
    _no_es_propio(con, actor_id, id_op)
    with transaccion(con):
        con.execute("DELETE FROM justificacion WHERE id_operador = ? AND id_horario = ? AND fecha = ?", (id_op, id_horario, fecha))
        bitacora(con, ahora, "administrador", actor_id, "quitar-justificacion", "operador", id_op, f"{fecha} horario {id_horario}")


def editar_estatus(con, id_op, fecha, id_horario, estado, motivo, actor_id, ahora, zona) -> None:
    _no_es_propio(con, actor_id, id_op)
    if estado not in ("asistencia", "retardo", "falta"):
        raise ErrorNegocio("estado-invalido", "El estatus debe ser asistencia, retardo o falta.")
    _fila_turno(con, id_op, fecha, id_horario, ahora, zona)
    with transaccion(con):
        con.execute("INSERT OR REPLACE INTO ajuste_estatus (id_operador, id_horario, fecha, estado, motivo, creado_ts, creado_por) VALUES (?,?,?,?,?,?,?)",
                    (id_op, id_horario, fecha, estado, motivo.strip(), ahora, actor_id))
        bitacora(con, ahora, "administrador", actor_id, "editar-estatus", "operador", id_op, f"{fecha} horario {id_horario} → {estado}")


def quitar_edicion(con, id_op, fecha, id_horario, actor_id, ahora) -> None:
    _no_es_propio(con, actor_id, id_op)
    with transaccion(con):
        con.execute("DELETE FROM ajuste_estatus WHERE id_operador = ? AND id_horario = ? AND fecha = ?", (id_op, id_horario, fecha))
        bitacora(con, ahora, "administrador", actor_id, "quitar-edicion", "operador", id_op, f"{fecha} horario {id_horario}")


# ---------- Datos personales y huellas ----------

def actualizar_operador(con, id_op: int, datos: dict, actor_id: int, ahora: int) -> None:
    for campo in ("nombres", "ap_paterno", "nacimiento", "expediente"):
        if not str(datos.get(campo, "")).strip():
            raise ErrorNegocio("datos-incompletos", f"Falta el campo «{campo}».")
    with transaccion(con):
        try:
            cur = con.execute(
                "UPDATE operador SET nombres = ?, ap_paterno = ?, ap_materno = ?, nacimiento = ?, expediente = ?, carrera = ? WHERE id = ?",
                (datos["nombres"].strip(), datos["ap_paterno"].strip(), datos.get("ap_materno", "").strip(), datos["nacimiento"],
                 datos["expediente"].strip(), datos.get("carrera", "").strip(), id_op))
        except sqlite3.IntegrityError:
            raise ErrorNegocio("expediente-repetido", "Ya existe un operador con ese expediente.", 409)
        if cur.rowcount == 0:
            raise ErrorNegocio("no-existe", "No existe ese operador.", 404)
        bitacora(con, ahora, "administrador", actor_id, "editar-operador", "operador", id_op)


def guardar_huella(con, plantilla: bytes, actor_id: int, ahora: int, id_operador: int | None = None, id_administrador: int | None = None) -> None:
    """Guarda (o reemplaza) la plantilla de huella de un operador o de un administrador."""
    columna, valor = ("id_operador", id_operador) if id_operador else ("id_administrador", id_administrador)
    with transaccion(con):
        con.execute(f"DELETE FROM huella WHERE {columna} = ?", (valor,))
        con.execute(f"INSERT INTO huella ({columna}, plantilla, creado_ts) VALUES (?,?,?)", (valor, plantilla, ahora))
        bitacora(con, ahora, "administrador", actor_id, "registrar-huella", "operador" if id_operador else "administrador", valor)
