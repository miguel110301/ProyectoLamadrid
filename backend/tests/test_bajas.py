"""Bajas: inactivo al instante, sin faltas durante la baja, reingreso y purga TOTAL a los 30 días."""
import pytest

from app.kiosko import Kiosko
from app.operadores import DIA_MS, dar_de_baja, dias_restantes_purga, purgar, reingresar
from app.reglas import Cfg, resumen
from app.seguridad import ErrorNegocio

from conftest import ZONA, ts

LUNES, LUNES2 = "2026-10-19", "2026-10-26"


def huella(con, op):
    con.execute("INSERT INTO huella (id_operador, plantilla, creado_ts) VALUES (?,?,0)", (op, b"plantilla"))


def test_baja_inmediata_no_genera_faltas_despues(con, operador, admin):
    dar_de_baja(con, operador, "renuncia", admin, ts(LUNES, "09:00"))   # a media mañana del lunes
    # El turno de las 07:00 ya había empezado: sigue contando. Los del 26 y siguientes ya no existen.
    r = resumen(con, operador, LUNES, "2026-11-30", ts("2026-11-30", "23:00"), Cfg(), ZONA)
    assert [f["fecha"] for f in r["filas"]] == [LUNES]


def test_baja_dos_veces_o_motivo_invalido(con, operador, admin):
    with pytest.raises(ErrorNegocio):
        dar_de_baja(con, operador, "capricho", admin, ts(LUNES, "09:00"))
    dar_de_baja(con, operador, "despido", admin, ts(LUNES, "09:00"))
    with pytest.raises(ErrorNegocio):
        dar_de_baja(con, operador, "despido", admin, ts(LUNES, "10:00"))


def test_operador_de_baja_ya_no_puede_registrar(con, operador, admin):
    huella(con, operador)
    dar_de_baja(con, operador, "renuncia", admin, ts(LUNES2, "06:00"))
    k = Kiosko(con, ZONA, reloj=lambda: ts(LUNES2, "07:00"))
    assert k.procesar(("operador", operador))["evento"] == "no-reconocida"
    assert con.execute("SELECT COUNT(*) c FROM registro_asistencia").fetchone()["c"] == 0


def test_reingreso_dentro_del_plazo_y_sin_faltas_del_hueco(con, operador, admin):
    dar_de_baja(con, operador, "otro", admin, ts("2026-10-20", "08:00"))
    reingresar(con, operador, admin, ts("2026-11-02", "08:00"))   # 13 días después, dentro del plazo de 30
    assert con.execute("SELECT activo FROM operador WHERE id = ?", (operador,)).fetchone()["activo"] == 1
    r = resumen(con, operador, "2026-10-20", "2026-11-09", ts("2026-11-09", "23:00"), Cfg(), ZONA)
    fechas = {f["fecha"] for f in r["filas"]}
    assert not fechas & {"2026-10-21", "2026-10-26", "2026-10-28", "2026-11-02"}   # el hueco de la baja no cuenta como faltas
    assert "2026-11-04" in fechas                                                   # desde el reingreso vuelve a tener turnos


def test_purga_a_los_30_dias_borra_todo(con, operador, admin):
    huella(con, operador)
    h = con.execute("SELECT id FROM horario WHERE id_operador = ?", (operador,)).fetchone()["id"]
    con.execute("INSERT INTO registro_asistencia (id_operador, id_horario, fecha, entrada_ts) VALUES (?,?,?,?)", (operador, h, LUNES, ts(LUNES, "07:00")))
    con.execute("INSERT INTO incidencia (id_operador,id_tipo,fecha,hora,registrado_ts,observacion) VALUES (?,?,?,?,?,?)",
                (operador, "otro", LUNES, "08:00", ts(LUNES, "08:00"), "algo"))
    baja = ts("2026-10-20", "10:00")
    dar_de_baja(con, operador, "despido", admin, baja)

    assert purgar(con, baja + 29 * DIA_MS) == []                     # el día 29 todavía se conserva
    assert dias_restantes_purga(con, operador, baja + 29 * DIA_MS) == 1
    assert purgar(con, baja + 30 * DIA_MS) == [operador]             # el día 30, se va todo

    for tabla in ("operador", "horario", "huella", "registro_asistencia", "incidencia", "periodo_baja", "justificacion", "ajuste_estatus"):
        assert con.execute(f"SELECT COUNT(*) c FROM {tabla}").fetchone()["c"] == 0, tabla
    restos = con.execute("SELECT accion, detalle FROM bitacora WHERE entidad = 'operador'").fetchall()
    assert [(f["accion"], f["detalle"]) for f in restos] == [("purga-operador", "datos eliminados")]   # solo el rastro, sin datos personales


def test_no_se_puede_reingresar_tras_la_purga(con, operador, admin):
    baja = ts("2026-10-20", "10:00")
    dar_de_baja(con, operador, "renuncia", admin, baja)
    purgar(con, baja + 31 * DIA_MS)
    with pytest.raises(ErrorNegocio):
        reingresar(con, operador, admin, baja + 32 * DIA_MS)
