"""Reglas de asistencia: umbrales 5/10 min y los casos del documento de requerimientos (20 min y 5 min)."""
from app.reglas import Cfg, estado_entrada, resumen

from conftest import ZONA, ts

LUNES = "2026-10-19"
CFG = Cfg()


def registrar(con, op, fecha, entrada, salida=None):
    h = con.execute("SELECT id FROM horario WHERE id_operador = ? AND dia_semana = ?", (op, 1)).fetchone()
    con.execute("INSERT INTO registro_asistencia (id_operador, id_horario, fecha, entrada_ts, salida_ts) VALUES (?,?,?,?,?)",
                (op, h["id"], fecha, ts(fecha, entrada), ts(fecha, salida) if salida else None))
    return h["id"]


def res(con, op, ahora):
    return resumen(con, op, LUNES, LUNES, ts(LUNES, ahora), CFG, ZONA)


def test_umbrales_de_entrada():
    ini = ts(LUNES, "07:00")
    assert estado_entrada(ini + 5 * 60_000, ini, CFG) == "a-tiempo"        # justo 5 min: a tiempo
    assert estado_entrada(ini + 5 * 60_000 + 1, ini, CFG) == "retardo"
    assert estado_entrada(ini + 10 * 60_000, ini, CFG) == "retardo"        # justo 10 min: retardo
    assert estado_entrada(ini + 10 * 60_000 + 1, ini, CFG) == "falta"


def test_caso_1_faltan_20_minutos(con, operador):
    registrar(con, operador, LUNES, "06:50", "11:30")   # 4 h 40 min sobre 5 h programadas
    r = res(con, operador, "13:00")
    assert r["filas"][0]["trabajado_min"] == 280 and r["filas"][0]["faltante_min"] == 20
    assert r["asistencias"] == 1 and r["faltas"] == 0


def test_caso_2_faltan_5_minutos(con, operador):
    registrar(con, operador, LUNES, "07:00", "11:55")
    assert res(con, operador, "13:00")["filas"][0]["faltante_min"] == 5


def test_sin_entrada_pasados_10_min_es_falta_de_turno_completo(con, operador):
    assert res(con, operador, "07:10")["faltas"] == 0     # aún dentro del límite: no aparece
    r = res(con, operador, "07:11")
    assert r["faltas"] == 1 and r["faltante_min"] == 300


def test_entrada_pasados_10_min_se_registra_pero_es_falta(con, operador):
    registrar(con, operador, LUNES, "07:15", "12:00")
    r = res(con, operador, "13:00")
    assert r["filas"][0]["estado"] == "falta" and r["faltas"] == 1 and r["asistencias"] == 0


def test_retardo_y_turno_incompleto(con, operador):
    registrar(con, operador, LUNES, "07:08", "11:00")
    f = res(con, operador, "13:00")["filas"][0]
    assert f["estado"] == "incompleto" and f["retardo"] and f["incompleto"]


def test_justificar_quita_la_falta_y_el_tiempo_faltante(con, operador, admin):
    from app.operadores import justificar
    hid = con.execute("SELECT id FROM horario WHERE id_operador = ? AND dia_semana = 1", (operador,)).fetchone()["id"]
    justificar(con, operador, LUNES, hid, "Consulta médica", admin, ts(LUNES, "14:00"), ZONA)
    r = res(con, operador, "14:00")
    assert r["faltas"] == 0 and r["justificadas"] == 1 and r["faltante_min"] == 0


def test_editar_estatus_manda_sobre_lo_calculado(con, operador, admin):
    from app.operadores import editar_estatus, quitar_edicion
    hid = registrar(con, operador, LUNES, "07:20", "12:00")      # falta tardía
    editar_estatus(con, operador, LUNES, hid, "retardo", "Fallo del sensor", admin, ts(LUNES, "13:00"), ZONA)
    r = res(con, operador, "13:00")
    assert r["filas"][0]["estado"] == "retardo" and r["faltas"] == 0 and r["asistencias"] == 1
    quitar_edicion(con, operador, LUNES, hid, admin, ts(LUNES, "13:05"))
    assert res(con, operador, "13:10")["faltas"] == 1


def test_no_se_justifica_una_asistencia_normal(con, operador, admin):
    import pytest
    from app.operadores import justificar
    from app.seguridad import ErrorNegocio
    hid = registrar(con, operador, LUNES, "07:00", "12:00")
    with pytest.raises(ErrorNegocio):
        justificar(con, operador, LUNES, hid, "x", admin, ts(LUNES, "13:00"), ZONA)
