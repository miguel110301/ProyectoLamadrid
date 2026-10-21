"""Administradores, sesiones y bloqueo por intentos."""
import pytest

from app import seguridad as seg
from app.seguridad import ErrorNegocio

from conftest import ts

T0 = ts("2026-10-19", "09:00")


def test_la_clave_no_se_guarda_en_claro(con, admin):
    h = con.execute("SELECT clave_hash FROM administrador").fetchone()["clave_hash"]
    assert "clave-segura-1" not in h and h.startswith("scrypt$")


def test_claves_debiles_rechazadas(con):
    for clave in ("admin", "corta", "ana.admin"):
        with pytest.raises(ErrorNegocio):
            seg.crear_administrador(con, "ana.admin", "Ana", clave, T0)


def test_login_correcto_y_sesion(con, admin):
    token = seg.iniciar_sesion(con, "ana.admin", "clave-segura-1", T0)
    assert seg.administrador_de_sesion(con, token, T0 + 1000)["id"] == admin
    assert con.execute("SELECT token_hash FROM sesion").fetchone()["token_hash"] != token   # solo se guarda el hash


def test_sin_token_o_token_falso_no_hay_sesion(con, admin):
    assert seg.administrador_de_sesion(con, None, T0) is None
    assert seg.administrador_de_sesion(con, "inventado", T0) is None


def test_sesion_caduca_por_inactividad(con, admin):
    token = seg.iniciar_sesion(con, "ana.admin", "clave-segura-1", T0)
    assert seg.administrador_de_sesion(con, token, T0 + seg.INACTIVIDAD_MS + 1) is None


def test_bloqueo_tras_5_intentos_fallidos(con, admin):
    for _ in range(5):
        with pytest.raises(ErrorNegocio):
            seg.iniciar_sesion(con, "ana.admin", "mal", T0)
    with pytest.raises(ErrorNegocio) as e:                                  # ni con la clave buena durante el bloqueo
        seg.iniciar_sesion(con, "ana.admin", "clave-segura-1", T0 + 1000)
    assert e.value.codigo == "bloqueado"
    assert seg.iniciar_sesion(con, "ana.admin", "clave-segura-1", T0 + seg.BLOQUEO_MS + 1)


def test_un_administrador_puede_crear_otro_y_queda_en_bitacora(con, admin):
    nuevo = seg.crear_administrador(con, "beto.admin", "Beto", "otra-clave-9", T0, creado_por=admin)
    assert seg.iniciar_sesion(con, "beto.admin", "otra-clave-9", T0)
    fila = con.execute("SELECT * FROM bitacora WHERE accion = 'crear-administrador' AND entidad_id = ?", (nuevo,)).fetchone()
    assert fila["actor_id"] == admin


def test_no_se_puede_desactivar_al_ultimo_administrador(con, admin):
    with pytest.raises(ErrorNegocio):
        seg.desactivar_administrador(con, admin, T0, admin)


def test_desactivar_cierra_sus_sesiones(con, admin):
    otro = seg.crear_administrador(con, "beto.admin", "Beto", "otra-clave-9", T0, creado_por=admin)
    token = seg.iniciar_sesion(con, "beto.admin", "otra-clave-9", T0)
    seg.desactivar_administrador(con, otro, T0 + 1, admin)
    assert seg.administrador_de_sesion(con, token, T0 + 2) is None


def test_cambiar_clave_cierra_sesiones_abiertas(con, admin):
    token = seg.iniciar_sesion(con, "ana.admin", "clave-segura-1", T0)
    seg.cambiar_clave(con, admin, "nueva-clave-77", T0 + 1, admin)
    assert seg.administrador_de_sesion(con, token, T0 + 2) is None
    assert seg.iniciar_sesion(con, "ana.admin", "nueva-clave-77", T0 + 3)
