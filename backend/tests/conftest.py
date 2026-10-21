import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db, seguridad  # noqa: E402
from app.operadores import alta_operador  # noqa: E402

ZONA = ZoneInfo("America/Mexico_City")


def ts(fecha: str, hhmm: str) -> int:
    """Milisegundos UTC de una fecha/hora local (2026-10-19 es lunes)."""
    y, m, d = map(int, fecha.split("-"))
    h, mi = map(int, hhmm.split(":"))
    return int(datetime(y, m, d, h, mi, tzinfo=ZONA).timestamp() * 1000)


@pytest.fixture
def con():
    c = db.conectar(":memory:")
    db.iniciar(c)
    yield c
    c.close()


@pytest.fixture
def admin(con):
    return seguridad.crear_administrador(con, "ana.admin", "Ana Admin", "clave-segura-1", ts("2026-10-01", "08:00"))


@pytest.fixture
def operador(con, admin):
    """Operador creado el lunes 2026-10-19 con turnos lunes 07:00–12:00 y miércoles 15:00–21:00."""
    ahora = ts("2026-10-19", "06:00")
    return alta_operador(
        con,
        {"nombres": "Juan Carlos", "ap_paterno": "Pérez", "ap_materno": "Hernández", "nacimiento": "2002-03-14", "expediente": "281045"},
        [{"dia_semana": 1, "hora_inicio": "07:00", "hora_fin": "12:00"}, {"dia_semana": 3, "hora_inicio": "15:00", "hora_fin": "21:00"}],
        admin, ahora, ZONA)
