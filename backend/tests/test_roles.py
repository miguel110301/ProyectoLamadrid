"""Superusuario, administrador que también opera y separación de funciones (nadie se favorece a sí mismo)."""
import pytest

from app import seguridad as seg
from app.kiosko import Kiosko
from app.operadores import cambiar_horario, dar_de_baja, editar_estatus, justificar, purgar, DIA_MS
from app.seguridad import ErrorNegocio

from conftest import ZONA, ts

LUNES = "2026-10-19"
T0 = ts(LUNES, "09:00")


@pytest.fixture
def sup(con):
    return seg.crear_administrador(con, "super", "Superusuario FRACTAL", "super-clave-77", T0, rol="superusuario")


def test_el_superusuario_solo_se_crea_desde_consola(con, admin):
    with pytest.raises(ErrorNegocio) as e:
        seg.crear_administrador(con, "otro.super", "X", "otra-clave-9", T0, creado_por=admin, rol="superusuario")
    assert e.value.codigo == "solo-consola"


def test_nadie_desactiva_ni_cambia_la_clave_del_superusuario(con, admin, sup):
    otro = seg.crear_administrador(con, "beto", "Beto", "beto-clave-9", T0, creado_por=admin)
    with pytest.raises(ErrorNegocio):
        seg.desactivar_administrador(con, sup, T0, otro)           # un administrador no puede
    with pytest.raises(ErrorNegocio) as e:
        seg.desactivar_administrador(con, sup, T0, sup)            # ni el propio superusuario
    assert e.value.codigo == "superusuario-protegido"
    with pytest.raises(ErrorNegocio) as e:
        seg.cambiar_clave(con, sup, "clave-del-intruso-1", T0, admin)
    assert e.value.codigo == "sin-permiso"
    seg.cambiar_clave(con, sup, "super-clave-nueva-2", T0, sup)    # solo él mismo


def test_el_superusuario_puede_restablecer_la_clave_de_un_administrador(con, admin, sup):
    seg.cambiar_clave(con, admin, "clave-restablecida-5", T0, sup)
    assert seg.iniciar_sesion(con, "ana.admin", "clave-restablecida-5", T0)


def test_un_administrador_no_puede_cambiar_la_clave_de_otro(con, admin):
    otro = seg.crear_administrador(con, "beto", "Beto", "beto-clave-9", T0, creado_por=admin)
    with pytest.raises(ErrorNegocio):
        seg.cambiar_clave(con, otro, "clave-del-intruso-1", T0, admin)


def test_administrador_que_tambien_opera_registra_su_propia_asistencia(con, admin, operador):
    a2 = seg.crear_administrador(con, "juan.coord", "Juan Carlos Pérez", "juan-clave-2026", T0, creado_por=admin, id_operador=operador)
    reloj = {"t": ts(LUNES, "06:58")}
    k = Kiosko(con, ZONA, reloj=lambda: reloj["t"])
    r = k.procesar(("administrador", a2))
    assert r["evento"] == "entrada" and r["operador"].startswith("Juan Carlos")
    reg = con.execute("SELECT id_operador FROM registro_asistencia").fetchone()
    assert reg["id_operador"] == operador


def test_administrador_sin_operador_no_registra_asistencia(con, admin):
    k = Kiosko(con, ZONA, reloj=lambda: T0)
    assert k.procesar(("administrador", admin))["evento"] == "administrador"
    assert con.execute("SELECT COUNT(*) c FROM registro_asistencia").fetchone()["c"] == 0


def test_un_operador_solo_puede_estar_ligado_a_una_cuenta(con, admin, operador):
    seg.crear_administrador(con, "a1", "A1", "clave-larga-1", T0, creado_por=admin, id_operador=operador)
    with pytest.raises(ErrorNegocio):
        seg.crear_administrador(con, "a2", "A2", "clave-larga-2", T0, creado_por=admin, id_operador=operador)


def test_conflicto_de_interes_no_puede_modificar_sus_propios_turnos(con, admin, operador):
    a2 = seg.crear_administrador(con, "juan.coord", "Juan Carlos", "juan-clave-2026", T0, creado_por=admin, id_operador=operador)
    hid = con.execute("SELECT id FROM horario WHERE id_operador = ? AND dia_semana = 1", (operador,)).fetchone()["id"]
    ahora = ts(LUNES, "14:00")
    for accion in (lambda: justificar(con, operador, LUNES, hid, "x", a2, ahora, ZONA),
                   lambda: editar_estatus(con, operador, LUNES, hid, "asistencia", "x", a2, ahora, ZONA),
                   lambda: cambiar_horario(con, operador, [{"dia_semana": 2, "hora_inicio": "07:00", "hora_fin": "09:00"}], "2026-10-27", a2, ahora),
                   lambda: dar_de_baja(con, operador, "otro", a2, ahora)):
        with pytest.raises(ErrorNegocio) as e:
            accion()
        assert e.value.codigo == "conflicto-de-interes"
    justificar(con, operador, LUNES, hid, "Consulta médica", admin, ahora, ZONA)   # otro administrador sí puede


def test_la_purga_desvincula_la_cuenta_de_administrador(con, admin, sup, operador):
    a2 = seg.crear_administrador(con, "juan.coord", "Juan Carlos", "juan-clave-2026", T0, creado_por=admin, id_operador=operador)
    dar_de_baja(con, operador, "renuncia", admin, T0)
    assert purgar(con, T0 + 31 * DIA_MS) == [operador]
    fila = con.execute("SELECT activo, id_operador FROM administrador WHERE id = ?", (a2,)).fetchone()
    assert fila["id_operador"] is None          # la cuenta sigue, pero sin datos del operador borrado
