"""Pantalla operativa: entrada/salida automáticas, rebote, apagones y saltos de reloj."""
import pytest

from app.kiosko import Kiosko
from app.seguridad import ErrorNegocio

from conftest import ZONA, ts

LUNES = "2026-10-19"


class Reloj:
    """Reloj controlable: pared (puede saltar) y monotónico (solo avanza)."""

    def __init__(self, fecha, hora):
        self.pared, self.mono = ts(fecha, hora), 1000.0

    def avanzar(self, seg):
        self.pared += int(seg * 1000)
        self.mono += seg


@pytest.fixture
def kiosko(con, operador):
    r = Reloj(LUNES, "06:58")
    k = Kiosko(con, ZONA, reloj=lambda: r.pared, mono=lambda: r.mono)
    k.r = r
    return k


def test_entrada_a_tiempo_y_salida_automatica(kiosko, operador):
    e = kiosko.procesar(("operador", operador))
    assert e["evento"] == "entrada" and e["llegada"] == "a-tiempo"
    kiosko.r.avanzar(5 * 3600 + 120)                     # 12:00 en punto
    s = kiosko.procesar(("operador", operador))
    assert s["evento"] == "salida" and s["trabajado_min"] == 302 and s["falto_min"] == 0


def test_la_segunda_lectura_en_15_s_es_el_mismo_toque(kiosko, operador):
    kiosko.procesar(("operador", operador))
    kiosko.r.avanzar(3)
    assert kiosko.procesar(("operador", operador))["evento"] == "duplicado"


def test_salida_anticipada_pide_confirmacion_y_usa_la_hora_de_la_confirmacion(kiosko, operador):
    kiosko.procesar(("operador", operador))
    kiosko.r.avanzar(3 * 3600)                           # 09:58, faltan 122 min
    c = kiosko.procesar(("operador", operador))
    assert c["evento"] == "confirmar-salida" and c["faltan_min"] == 122
    kiosko.r.avanzar(10)
    s = kiosko.confirmar_salida(True)
    assert s["evento"] == "salida"
    reg = kiosko.con.execute("SELECT * FROM registro_asistencia").fetchone()
    assert reg["salida_anticipada"] == 1 and reg["salida_ts"] == kiosko.r.pared


def test_cancelar_la_salida_deja_la_entrada_abierta(kiosko, operador):
    kiosko.procesar(("operador", operador))
    kiosko.r.avanzar(3 * 3600)
    kiosko.procesar(("operador", operador))
    assert kiosko.confirmar_salida(False)["evento"] == "salida-cancelada"
    assert kiosko.con.execute("SELECT salida_ts FROM registro_asistencia").fetchone()["salida_ts"] is None
    with pytest.raises(ErrorNegocio):
        kiosko.confirmar_salida(True)                    # ya no hay nada pendiente


def test_sin_turno_no_registra_nada(kiosko, operador):
    kiosko.r.pared = ts("2026-10-20", "10:00")           # martes: sin turno
    assert kiosko.procesar(("operador", operador))["evento"] == "sin-turno"
    assert kiosko.con.execute("SELECT COUNT(*) c FROM registro_asistencia").fetchone()["c"] == 0


def test_huella_no_reconocida_y_administrador_no_registran_asistencia(kiosko):
    assert kiosko.procesar(None)["evento"] == "no-reconocida"
    assert kiosko.procesar(("administrador", 1))["evento"] == "administrador"
    assert kiosko.con.execute("SELECT COUNT(*) c FROM registro_asistencia").fetchone()["c"] == 0


def test_reinicio_por_apagon_no_duplica_la_lectura(con, operador):
    """Tras reiniciar no hay memoria del rebote: la base lo evita (y su índice único impide duplicar el turno)."""
    r = Reloj(LUNES, "06:58")
    Kiosko(con, ZONA, reloj=lambda: r.pared, mono=lambda: r.mono).procesar(("operador", operador))
    r.avanzar(4)
    k2 = Kiosko(con, ZONA, reloj=lambda: r.pared, mono=lambda: r.mono)       # servidor nuevo, sin memoria
    assert k2.procesar(("operador", operador))["evento"] == "duplicado"


def test_salto_de_reloj_hacia_atras_no_deja_la_salida_antes_de_la_entrada(kiosko, operador):
    kiosko.procesar(("operador", operador))
    kiosko.r.avanzar(4 * 3600 + 3000)
    kiosko.procesar(("operador", operador))              # 11:48 → confirma
    kiosko.r.pared -= 3 * 3600 * 1000                    # el reloj retrocede 3 h al resincronizar
    kiosko.confirmar_salida(True)
    reg = kiosko.con.execute("SELECT * FROM registro_asistencia").fetchone()
    assert reg["salida_ts"] >= reg["entrada_ts"]


def test_incidencia_se_envia_con_la_huella_del_operador(kiosko, operador):
    kiosko.preparar_incidencia({"tipo": "corte-cfe", "hora": "07:30", "programa": "Noticiero", "duracion_min": 12, "observacion": "Se fue la luz"})
    assert kiosko.con.execute("SELECT COUNT(*) c FROM incidencia").fetchone()["c"] == 0   # aún sin huella
    r = kiosko.procesar(("operador", operador))
    assert r["evento"] == "incidencia-registrada"
    inc = kiosko.con.execute("SELECT * FROM incidencia").fetchone()
    assert inc["id_operador"] == operador and inc["duracion_min"] == 12
    assert kiosko.con.execute("SELECT COUNT(*) c FROM registro_asistencia").fetchone()["c"] == 0   # no cuenta como entrada


def test_con_el_formulario_abierto_la_huella_nunca_cuenta_como_entrada(kiosko, operador):
    """Si la incidencia está incompleta, la huella solo avisa: no debe registrar una entrada por accidente."""
    kiosko.abrir_incidencia()
    assert kiosko.procesar(("operador", operador))["evento"] == "incidencia-incompleta"
    assert kiosko.con.execute("SELECT COUNT(*) c FROM registro_asistencia").fetchone()["c"] == 0
    kiosko.cancelar_incidencia()                       # al cerrar el formulario vuelve la operación normal
    kiosko.r.avanzar(20)
    assert kiosko.procesar(("operador", operador))["evento"] == "entrada"


def test_si_el_formulario_deja_de_mandar_latidos_se_da_por_cerrado(kiosko, operador):
    kiosko.abrir_incidencia()
    kiosko.r.avanzar(601)
    assert kiosko.procesar(("operador", operador))["evento"] in ("entrada", "sin-turno")


def test_incidencia_invalida(kiosko):
    for datos in ({"tipo": "inventado", "hora": "07:30", "observacion": "x"},
                  {"tipo": "otro", "hora": "7:3", "observacion": "x", "duracion_min": 5},
                  {"tipo": "otro", "hora": "07:30", "observacion": "  ", "duracion_min": 5},
                  {"tipo": "corte-cfe", "hora": "07:30", "observacion": "x"}):      # falta la duración
        with pytest.raises(ErrorNegocio):
            kiosko.preparar_incidencia(datos)
