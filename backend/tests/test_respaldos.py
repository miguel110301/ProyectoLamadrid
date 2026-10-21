"""Respaldos: copia consistente y verificada, rotación, USB ausente y restauración."""
import sqlite3
from datetime import datetime, timedelta

import pytest

from app import config, db, respaldos
from app.operadores import alta_operador

from conftest import ZONA, ts


def entorno(tmp_path, usb=True):
    return config.Entorno(ruta_db=tmp_path / "t.db", zona_horaria="America/Mexico_City", simulador=False, host="127.0.0.1",
                          respaldo_local=tmp_path / "local", respaldo_usb=(tmp_path / "usb" / "TvUAQ") if usb else None)


@pytest.fixture
def base(tmp_path, admin_en_disco=None):
    con = db.conectar(tmp_path / "t.db")
    db.iniciar(con)
    from app import seguridad
    seguridad.crear_administrador(con, "ana.admin", "Ana", "clave-segura-1", ts("2026-10-01", "08:00"))
    yield con
    con.close()


def test_copia_consistente_y_verificada(tmp_path, base):
    info = respaldos.crear_copia(base, tmp_path / "local", ts("2026-10-20", "02:00"), ZONA)
    copia = sqlite3.connect(tmp_path / "local" / info["archivo"])
    assert copia.execute("SELECT usuario FROM administrador").fetchone()[0] == "ana.admin"
    assert copia.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert len(info["sha256"]) == 64 and not list((tmp_path / "local").glob("*.parcial"))


def test_respalda_en_local_y_usb_y_queda_en_historial(tmp_path, base):
    (tmp_path / "usb").mkdir()
    res = respaldos.respaldar_todo(base, entorno(tmp_path), ts("2026-10-20", "02:00"), ZONA)
    assert [r["ok"] for r in res] == [True, True]
    assert len(list((tmp_path / "usb" / "TvUAQ").glob("tvuaq-*.db"))) == 1
    assert base.execute("SELECT COUNT(*) c FROM respaldo WHERE ok = 1").fetchone()["c"] == 2


def test_usb_desconectada_no_rompe_y_avisa(tmp_path, base):
    # la carpeta madre de la USB no existe: la unidad no está conectada
    res = respaldos.respaldar_todo(base, entorno(tmp_path), ts("2026-10-20", "02:00"), ZONA)
    local, usb = res
    assert local["ok"] is True and usb["ok"] is False and "No disponible" in usb["detalle"]
    est = respaldos.estado(base, entorno(tmp_path), ts("2026-10-20", "03:00"))
    assert est["destinos"][1]["alerta"] and not est["destinos"][0]["alerta"]


def test_sin_usb_configurada_se_indica(tmp_path, base):
    est = respaldos.estado(base, entorno(tmp_path, usb=False), ts("2026-10-20", "03:00"))
    assert est["destinos"][1]["configurado"] is False and "USB" in est["destinos"][1]["alerta"]


def test_alerta_cuando_el_ultimo_respaldo_es_viejo(tmp_path, base):
    (tmp_path / "usb").mkdir()
    respaldos.respaldar_todo(base, entorno(tmp_path), ts("2026-10-20", "02:00"), ZONA)
    assert not any(d["alerta"] for d in respaldos.estado(base, entorno(tmp_path), ts("2026-10-21", "02:00"))["destinos"])
    est = respaldos.estado(base, entorno(tmp_path), ts("2026-10-24", "02:00"))   # 4 días después
    assert all(d["alerta"] for d in est["destinos"])


def test_rotacion_conserva_7_diarios_y_4_semanales(tmp_path):
    carpeta = tmp_path / "c"
    carpeta.mkdir()
    dia = datetime(2026, 8, 1, 2, 0)
    for i in range(90):                      # 90 días de respaldos diarios
        (carpeta / f"tvuaq-{dia + timedelta(days=i):%Y%m%d-%H%M%S}.db").write_bytes(b"x")
    (carpeta / "notas.txt").write_text("no es nuestro")
    respaldos.rotar(carpeta, ZONA)
    quedan = sorted(p.name for p in carpeta.glob("tvuaq-*.db"))
    assert 8 <= len(quedan) <= 11            # 7 diarios + hasta 4 semanales (algunos coinciden)
    assert quedan[-1].startswith("tvuaq-20261029")   # el más reciente siempre se conserva
    assert (carpeta / "notas.txt").exists()          # lo que no es un respaldo no se toca


def test_cuando_toca_respaldar(tmp_path, base):
    assert respaldos.debe_respaldar(base, ts("2026-10-20", "09:00"), ZONA)            # nunca hubo
    respaldos.respaldar_todo(base, entorno(tmp_path), ts("2026-10-20", "02:00"), ZONA)
    assert not respaldos.debe_respaldar(base, ts("2026-10-20", "15:00"), ZONA)
    assert not respaldos.debe_respaldar(base, ts("2026-10-21", "00:30"), ZONA)        # aún no es la hora
    assert respaldos.debe_respaldar(base, ts("2026-10-21", "02:30"), ZONA)            # ya pasaron ~24 h y es de madrugada
    assert respaldos.debe_respaldar(base, ts("2026-10-22", "15:00"), ZONA)            # apagado varios días: al arrancar se pone al corriente


def test_restaurar_reemplaza_y_conserva_la_base_anterior(tmp_path, base):
    info = respaldos.crear_copia(base, tmp_path / "local", ts("2026-10-20", "02:00"), ZONA)
    base.execute("DELETE FROM administrador")            # "desastre": se pierde todo
    base.close()
    previa = respaldos.restaurar(tmp_path / "local" / info["archivo"], tmp_path / "t.db")
    assert previa.exists()
    c = sqlite3.connect(tmp_path / "t.db")
    assert c.execute("SELECT COUNT(*) FROM administrador").fetchone()[0] == 1


def test_no_restaura_un_respaldo_danado(tmp_path):
    malo = tmp_path / "malo.db"
    malo.write_bytes(b"esto no es una base de datos")
    with pytest.raises(ValueError):
        respaldos.restaurar(malo, tmp_path / "t.db")
    assert not (tmp_path / "t.db").exists()              # no se tocó nada
