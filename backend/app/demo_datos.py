"""Base de DEMOSTRACIÓN con datos ficticios (4 operadores activos, 1 dado de baja, 28 días de historial).

    TVUAQ_DB=data/demo.db python -m app.demo_datos --reiniciar

Nunca toca la base real: se niega a borrar un archivo cuyo nombre no contenga «demo».
Administrador de la demo: usuario `demo` · contraseña `demo-tvuaq-26` (también tiene huella en el simulador).
"""
import random
import sys
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from . import config, db, seguridad
from .reglas import MIN, a_ts, dia_semana

USUARIO, CLAVE = "demo", "demo-tvuaq-26"

OPERADORES = [
    ("Juan Carlos", "Pérez", "Hernández", "2002-03-14", "281045", "Comunicación y Periodismo", [(1, "07:00", "12:00"), (3, "15:00", "21:00")]),
    ("María Fernanda", "López", "Ruiz", "2001-11-02", "279318", "Diseño y Producción Audiovisual", [(2, "07:00", "13:00"), (4, "07:00", "13:00")]),
    ("Luis Eduardo", "Ramírez", "Soto", "2003-07-21", "290772", "Ingeniería de Software", [(1, "17:00", "21:00"), (3, "17:00", "21:00"), (5, "17:00", "21:00")]),
    ("Ana Sofía", "Martínez", "Vega", "2000-01-30", "271904", "Ingeniería en Telecomunicaciones y Redes", [(2, "13:00", "19:00"), (5, "07:00", "13:00")]),
]
# Dado de baja hace 5 días: aparece en «Ver bajas» con sus días restantes antes del borrado
BAJA = ("Pedro Alonso", "Gutiérrez", "Mora", "2002-09-09", "285511", "Ingeniería Civil", [(1, "13:00", "17:00"), (4, "13:00", "17:00")])

OBSERVACIONES = {
    "corte-cfe": "Se fue la luz de CFE en el edificio; entró la planta de emergencia.",
    "falla-energia": "Disparo del UPS de rack principal; se reinició y se verificó la señal.",
    "falla-equipo": "El servidor de reproducción dejó de responder; se reinició el equipo.",
    "pauta-rtc": "Se sustituyó la pauta por solicitud de Radio y Televisión de Querétaro.",
    "pauta-ine": "Se sustituyó la pauta conforme al oficio vigente del INE.",
    "ajuste-prog": "Se recorrió el bloque de programación por transmisión especial.",
    "falla-programa": "El videoclip se congeló a mitad de la reproducción; se cargó el respaldo.",
    "otro": "Intermitencia en el enlace de retorno; se notificó a soporte.",
}
MOTIVOS = ["Consulta médica", "Examen en la facultad", "Permiso de la coordinación"]
PROGRAMAS = ["Noticiero", "Barra infantil", "Cápsulas culturales", "Deportes UAQ", ""]


def poblar(con, zona: ZoneInfo, ahora: int | None = None, dias: int = 28) -> None:
    ahora = ahora or int(time.time() * 1000)
    rnd = random.Random(20261013)
    entre = lambda a, b: rnd.randint(a, b)  # noqa: E731
    hoy = datetime.fromtimestamp(ahora / 1000, zona).date()
    alta = (hoy - timedelta(days=dias)).isoformat()

    adm = seguridad.crear_administrador(con, USUARIO, "Administrador de demostración", CLAVE, ahora)
    con.execute("INSERT INTO huella (id_administrador, plantilla, creado_ts) VALUES (?,?,?)", (adm, b"demo", ahora))
    tipos = [f["id"] for f in con.execute("SELECT id FROM tipo_incidencia")]
    requieren = {f["id"] for f in con.execute("SELECT id FROM tipo_incidencia WHERE requiere_duracion = 1")}

    baja_ts = int(datetime.combine(hoy - timedelta(days=5), datetime.min.time(), tzinfo=zona).timestamp() * 1000) + 12 * 3600_000

    for datos in OPERADORES + [BAJA]:
        nombres, ap_p, ap_m, nac, exp, carrera, turnos = datos
        de_baja = datos is BAJA
        op = con.execute("INSERT INTO operador (nombres, ap_paterno, ap_materno, nacimiento, expediente, carrera, alta_fecha, activo) VALUES (?,?,?,?,?,?,?,?)",
                         (nombres, ap_p, ap_m, nac, exp, carrera, alta, 0 if de_baja else 1)).lastrowid
        con.execute("INSERT INTO huella (id_operador, plantilla, creado_ts) VALUES (?,?,?)", (op, b"demo", ahora))
        horarios = {}
        for dia, ini, fin in turnos:
            horarios[dia] = horarios.get(dia, []) + [(con.execute(
                "INSERT INTO horario (id_operador, dia_semana, hora_inicio, hora_fin, vigente_desde) VALUES (?,?,?,?,?)",
                (op, dia, ini, fin, alta)).lastrowid, ini, fin)]
        if de_baja:
            con.execute("INSERT INTO periodo_baja (id_operador, desde_ts, motivo, baja_por) VALUES (?,?,?,?)", (op, baja_ts, "renuncia", adm))

        for atras in range(dias, 0, -1):
            d = hoy - timedelta(days=atras)
            fecha = d.isoformat()
            for id_h, ini, fin in horarios.get(dia_semana(fecha), []):
                ini_ts, fin_ts = a_ts(fecha, ini, zona), a_ts(fecha, fin, zona)
                if de_baja and ini_ts >= baja_ts:
                    continue
                r = rnd.random()
                ent, sal = ini_ts + entre(-10, 5) * MIN, fin_ts + entre(0, 8) * MIN
                if 0.65 <= r < 0.75:
                    ent = ini_ts + entre(6, 10) * MIN                      # retardo
                elif 0.75 <= r < 0.82:
                    ent, sal = ini_ts + entre(6, 10) * MIN, fin_ts - entre(10, 40) * MIN   # retardo + salida temprana
                elif 0.82 <= r < 0.88:
                    sal = fin_ts - entre(8, 40) * MIN                      # solo salida temprana
                elif r >= 0.88:
                    if rnd.random() < 0.4:                                 # falta ya justificada
                        con.execute("INSERT INTO justificacion (id_operador, id_horario, fecha, motivo, creado_ts, creado_por) VALUES (?,?,?,?,?,?)",
                                    (op, id_h, fecha, MOTIVOS[entre(0, 2)], fin_ts + 3600_000, adm))
                    if r >= 0.94:
                        continue                                           # no vino
                    ent = ini_ts + entre(11, 25) * MIN                     # llegó pasados 10 min: entrada con falta
                con.execute("INSERT INTO registro_asistencia (id_operador, id_horario, fecha, entrada_ts, salida_ts, salida_anticipada) VALUES (?,?,?,?,?,?)",
                            (op, id_h, fecha, ent, sal, int(sal < fin_ts - 3 * MIN)))
                if rnd.random() < 0.18:
                    tipo = tipos[entre(0, len(tipos) - 1)]
                    mins = int(ini[:2]) * 60 + int(ini[3:]) + entre(20, max(21, (int(fin[:2]) * 60 + int(fin[3:])) - (int(ini[:2]) * 60 + int(ini[3:])) - 20))
                    hora = f"{mins // 60:02d}:{mins % 60:02d}"
                    con.execute("INSERT INTO incidencia (id_operador, id_tipo, fecha, hora, registrado_ts, programa, duracion_min, observacion) VALUES (?,?,?,?,?,?,?,?)",
                                (op, tipo, fecha, hora, a_ts(fecha, hora, zona) + entre(1, 12) * MIN, PROGRAMAS[entre(0, 4)],
                                 entre(2, 45) if tipo in requieren else None, OBSERVACIONES[tipo]))


def main() -> int:
    entorno = config.cargar()
    ruta = entorno.ruta_db
    if "demo" not in ruta.name.lower():
        print(f"Me niego a poblar «{ruta}»: el nombre del archivo debe contener «demo» para no tocar datos reales.")
        return 1
    if "--reiniciar" in sys.argv:
        for sufijo in ("", "-wal", "-shm"):
            ruta.with_name(ruta.name + sufijo).unlink(missing_ok=True)
    con = db.conectar(ruta)
    db.iniciar(con)
    if con.execute("SELECT COUNT(*) c FROM operador").fetchone()["c"]:
        print("La base de demostración ya tiene datos (usa --reiniciar para empezar de cero).")
        return 0
    poblar(con, ZoneInfo(entorno.zona_horaria))
    print(f"Base de demostración lista en {ruta}\nAdministrador: {USUARIO} / {CLAVE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
