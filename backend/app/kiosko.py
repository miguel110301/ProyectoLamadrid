"""Pantalla operativa: qué pasa cuando llega una lectura de huella.

El navegador NUNCA dice quién es la persona: la identidad viene del lector. El operador solo puede registrar
entrada, salida o una incidencia propia; no hay forma de que, desde aquí, se toque algo administrativo.
"""
import re
import time
from zoneinfo import ZoneInfo

from .db import transaccion
from .lector import Persona
from .reglas import MIN, Cfg, a_ts, estado_entrada, fecha_de, registro_vigente, turno_para_entrada
from .seguridad import ErrorNegocio, bitacora

CONFIRMAR_SALIDA_S = 30     # tiempo para aceptar "aún no termina tu turno"
INCIDENCIA_ESPERA_S = 600   # el formulario de incidencia abierto manda latidos; sin ellos se da por cerrado
HORA = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def _ms() -> int:
    return time.time_ns() // 1_000_000


class Kiosko:
    def __init__(self, con, zona: ZoneInfo, reloj=_ms, mono=time.monotonic):
        self.con, self.zona, self.reloj, self.mono = con, zona, reloj, mono
        self._ultima_lectura: dict[int, float] = {}   # operador → reloj monotónico (inmune a saltos de hora)
        self._confirmacion: dict | None = None
        self._incidencia: dict | None = None

    def olvidar_lecturas(self) -> None:
        """Solo para la demostración: al mover la hora del sistema, el antirrebote vuelve a empezar."""
        self._ultima_lectura.clear()

    # ---------- lectura de huella ----------
    def procesar(self, persona: Persona) -> dict:
        ahora = self.reloj()
        if persona is None:
            return {"evento": "no-reconocida"}
        tipo, ident = persona
        if tipo == "administrador":
            # Un administrador que también es operador registra su propia asistencia e incidencias con su huella
            enlace = self.con.execute(
                "SELECT a.id_operador FROM administrador a JOIN operador o ON o.id = a.id_operador AND o.activo = 1 "
                "WHERE a.id = ? AND a.activo = 1", (ident,)).fetchone()
            if enlace is None:
                return {"evento": "administrador", "id_administrador": ident}
            ident = enlace["id_operador"]

        op = self.con.execute("SELECT * FROM operador WHERE id = ? AND activo = 1", (ident,)).fetchone()
        if op is None:   # baja o inexistente: aunque el lector lo reconociera, no puede registrar nada
            return {"evento": "no-reconocida"}
        nombre = f"{op['nombres']} {op['ap_paterno']} {op['ap_materno']}".strip()
        cfg = Cfg.desde_db(self.con)

        # Con el formulario de incidencia abierto, la huella NUNCA cuenta como entrada ni salida:
        # envía la incidencia si está completa, o avisa que falta llenarla.
        inc = self._incidencia_activa()
        if inc:
            if inc["datos"] is None:
                return {"evento": "incidencia-incompleta", "operador": nombre}
            return self._guardar_incidencia(op, nombre, ahora)

        if self._es_rebote(op["id"], ahora, cfg):
            return {"evento": "duplicado", "operador": nombre}
        self._ultima_lectura[op["id"]] = self.mono()

        vigente = registro_vigente(self.con, op["id"], ahora, cfg, self.zona)
        return self._salida(op, nombre, vigente, ahora, cfg) if vigente else self._entrada(op, nombre, ahora, cfg)

    def _es_rebote(self, id_op: int, ahora: int, cfg: Cfg) -> bool:
        previa = self._ultima_lectura.get(id_op)
        if previa is not None:
            return self.mono() - previa < cfg.rebote_seg
        # Tras un reinicio no hay memoria: se usa la última marca guardada (con valor absoluto por si cambió la hora)
        fila = self.con.execute(
            "SELECT MAX(MAX(entrada_ts), COALESCE(MAX(salida_ts), 0)) u FROM registro_asistencia WHERE id_operador = ?", (id_op,)).fetchone()
        return bool(fila["u"]) and abs(ahora - fila["u"]) < cfg.rebote_seg * 1000

    def _entrada(self, op, nombre, ahora, cfg) -> dict:
        t = turno_para_entrada(self.con, op["id"], ahora, cfg, self.zona)
        if t is None:
            return {"evento": "sin-turno", "operador": nombre, "anticipo_min": cfg.anticipo_entrada_min}
        with transaccion(self.con):
            self.con.execute("INSERT INTO registro_asistencia (id_operador, id_horario, fecha, entrada_ts) VALUES (?,?,?,?)",
                             (op["id"], t["id_horario"], t["fecha"], ahora))
        llegada = estado_entrada(ahora, t["ini_ts"], cfg)
        return {"evento": "entrada", "operador": nombre, "ts": ahora, "llegada": llegada,
                "min_tarde": round((ahora - t["ini_ts"]) / MIN), "turno": f"{t['inicio']}–{t['fin']}"}

    def _salida(self, op, nombre, vigente, ahora, cfg) -> dict:
        reg, t = vigente
        faltan = (t["fin_ts"] - ahora) / MIN
        if faltan > cfg.tolerancia_salida_min:
            self._confirmacion = {"id_registro": reg["id"], "id_operador": op["id"], "nombre": nombre,
                                  "expira": self.mono() + CONFIRMAR_SALIDA_S}
            return {"evento": "confirmar-salida", "operador": nombre, "faltan_min": int(-(-faltan // 1))}
        return self._cerrar(reg["id"], nombre, ahora, anticipada=False)

    def confirmar_salida(self, aceptar: bool) -> dict:
        c, self._confirmacion = self._confirmacion, None
        if c is None or self.mono() > c["expira"]:
            raise ErrorNegocio("sin-confirmacion", "No hay una salida esperando confirmación.", 409)
        if not aceptar:
            return {"evento": "salida-cancelada"}
        return self._cerrar(c["id_registro"], c["nombre"], self.reloj(), anticipada=True)  # hora real: la de la confirmación

    def _cerrar(self, id_registro: int, nombre: str, ts: int, anticipada: bool) -> dict:
        reg = self.con.execute("SELECT * FROM registro_asistencia WHERE id = ? AND salida_ts IS NULL", (id_registro,)).fetchone()
        if reg is None:
            raise ErrorNegocio("sin-entrada", "Esa entrada ya no está abierta.", 409)
        ts = max(ts, reg["entrada_ts"])  # un salto de reloj hacia atrás no puede dejar la salida antes de la entrada
        with transaccion(self.con):
            self.con.execute("UPDATE registro_asistencia SET salida_ts = ?, salida_anticipada = ? WHERE id = ?",
                             (ts, int(anticipada), id_registro))
        h = self.con.execute("SELECT hora_inicio, hora_fin FROM horario WHERE id = ?", (reg["id_horario"],)).fetchone()
        prog = (a_ts(reg["fecha"], h["hora_fin"], self.zona) - a_ts(reg["fecha"], h["hora_inicio"], self.zona)) / MIN
        trabajado = round((ts - reg["entrada_ts"]) / MIN)
        return {"evento": "salida", "operador": nombre, "ts": ts, "trabajado_min": trabajado, "falto_min": max(0, prog - trabajado)}

    # ---------- incidencias ----------
    def _incidencia_activa(self):
        if self._incidencia and self.mono() <= self._incidencia["expira"]:
            return self._incidencia
        self._incidencia = None
        return None

    def abrir_incidencia(self) -> None:
        """El formulario se abrió (o manda un latido): mientras siga abierto, las huellas no registran entrada/salida."""
        inc = self._incidencia_activa()
        if inc:
            inc["expira"] = self.mono() + INCIDENCIA_ESPERA_S
        else:
            self._incidencia = {"datos": None, "expira": self.mono() + INCIDENCIA_ESPERA_S}

    def preparar_incidencia(self, datos: dict) -> None:
        """Valida el formulario completo; queda listo para enviarse con la huella de quien la registra."""
        tipo = self.con.execute("SELECT * FROM tipo_incidencia WHERE id = ?", (datos.get("tipo"),)).fetchone()
        if tipo is None:
            raise ErrorNegocio("tipo-invalido", "Elige un tipo de incidencia.")
        if not HORA.match(str(datos.get("hora", ""))):
            raise ErrorNegocio("hora-invalida", "La hora de la incidencia no es válida.")
        if not str(datos.get("observacion", "")).strip():
            raise ErrorNegocio("observacion-obligatoria", "Describe la incidencia.")
        dur = datos.get("duracion_min")
        if tipo["requiere_duracion"] and not (isinstance(dur, int) and dur > 0):
            raise ErrorNegocio("duracion-obligatoria", "Indica la duración de la incidencia.")
        self.abrir_incidencia()
        self._incidencia["datos"] = {**datos, "duracion_min": dur if tipo["requiere_duracion"] else None}

    def borrar_borrador(self) -> None:
        """El formulario quedó incompleto: sigue abierto, pero ya no hay nada que enviar."""
        inc = self._incidencia_activa()
        if inc:
            inc["datos"] = None

    def cancelar_incidencia(self) -> None:
        self._incidencia = None

    def _guardar_incidencia(self, op, nombre, ahora) -> dict:
        d, self._incidencia = self._incidencia["datos"], None
        with transaccion(self.con):
            self.con.execute(
                "INSERT INTO incidencia (id_operador, id_tipo, fecha, hora, registrado_ts, programa, duracion_min, observacion) VALUES (?,?,?,?,?,?,?,?)",
                (op["id"], d["tipo"], fecha_de(ahora, self.zona), d["hora"], ahora, str(d.get("programa", "")).strip(),
                 d["duracion_min"], d["observacion"].strip()))
            bitacora(self.con, ahora, "operador", op["id"], "incidencia", "operador", op["id"])
        return {"evento": "incidencia-registrada", "operador": nombre, "ts": ahora}
