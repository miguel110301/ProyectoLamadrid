"""Administradores, claves y sesiones. Solo un administrador con sesión válida puede tocar la parte administrativa."""
import base64
import hashlib
import hmac
import secrets
import sqlite3

from .db import transaccion

N, R, P = 2**14, 8, 1
MIN_CLAVE = 8
MAX_INTENTOS = 5
BLOQUEO_MS = 5 * 60_000
INACTIVIDAD_MS = 30 * 60_000      # la sesión caduca tras 30 min sin usarse
DURACION_MAX_MS = 12 * 3600_000   # y nunca dura más de 12 h


class ErrorNegocio(Exception):
    """Error esperado de una regla; se traduce a una respuesta HTTP clara para el usuario."""

    def __init__(self, codigo: str, mensaje: str, http: int = 400):
        super().__init__(mensaje)
        self.codigo, self.mensaje, self.http = codigo, mensaje, http


def hash_clave(clave: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(clave.encode(), salt=sal, n=N, r=R, p=P, dklen=32)
    return "scrypt${}${}${}${}${}".format(N, R, P, base64.b64encode(sal).decode(), base64.b64encode(h).decode())


def verificar_clave(clave: str, almacenado: str) -> bool:
    try:
        _, n, r, p, sal, esperado = almacenado.split("$")
        h = hashlib.scrypt(clave.encode(), salt=base64.b64decode(sal), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(h, base64.b64decode(esperado))
    except (ValueError, TypeError):
        return False


def validar_clave(clave: str, usuario: str = "") -> None:
    if len(clave) < MIN_CLAVE:
        raise ErrorNegocio("clave-corta", f"La contraseña debe tener al menos {MIN_CLAVE} caracteres.")
    if clave.lower() in {"admin", "password", "12345678", usuario.lower()}:
        raise ErrorNegocio("clave-debil", "Esa contraseña es demasiado fácil de adivinar.")


def bitacora(con, ts, actor_tipo, actor_id, accion, entidad=None, entidad_id=None, detalle=""):
    con.execute(
        "INSERT INTO bitacora (ts, actor_tipo, actor_id, accion, entidad, entidad_id, detalle) VALUES (?,?,?,?,?,?,?)",
        (ts, actor_tipo, actor_id, accion, entidad, entidad_id, detalle))


ROLES = ("administrador", "superusuario")


def _rol_de(con, id_administrador: int) -> str | None:
    f = con.execute("SELECT rol FROM administrador WHERE id = ?", (id_administrador,)).fetchone()
    return f["rol"] if f else None


def crear_administrador(con, usuario: str, nombre: str, clave: str, ahora: int, creado_por: int | None = None,
                        rol: str = "administrador", id_operador: int | None = None) -> int:
    """Crea un administrador. El primero y el superusuario (creado_por=None) solo se crean desde la consola de la PC (app/crear_admin.py).

    Con `id_operador`, el administrador también es un operador: su huella registra su propia entrada, salida e incidencias.
    """
    usuario, nombre = usuario.strip(), nombre.strip()
    if not usuario or not nombre:
        raise ErrorNegocio("datos-incompletos", "Usuario y nombre son obligatorios.")
    if rol not in ROLES:
        raise ErrorNegocio("rol-invalido", "Rol no válido.")
    if rol == "superusuario" and creado_por is not None:
        raise ErrorNegocio("solo-consola", "El superusuario solo se crea desde la consola de la PC.", 403)
    validar_clave(clave, usuario)
    if id_operador is not None:
        op = con.execute("SELECT activo FROM operador WHERE id = ?", (id_operador,)).fetchone()
        if op is None or not op["activo"]:
            raise ErrorNegocio("operador-invalido", "Ese operador no existe o está dado de baja.")
        if con.execute("SELECT 1 FROM administrador WHERE id_operador = ?", (id_operador,)).fetchone():
            raise ErrorNegocio("operador-ya-vinculado", "Ese operador ya tiene una cuenta de administrador.", 409)
    with transaccion(con):
        try:
            cur = con.execute(
                "INSERT INTO administrador (usuario, nombre, clave_hash, creado_ts, creado_por, rol, id_operador) VALUES (?,?,?,?,?,?,?)",
                (usuario, nombre, hash_clave(clave), ahora, creado_por, rol, id_operador))
        except sqlite3.IntegrityError:
            raise ErrorNegocio("usuario-repetido", "Ya existe un administrador con ese usuario.", 409)
        bitacora(con, ahora, "administrador" if creado_por else "sistema", creado_por, "crear-" + rol,
                 "administrador", cur.lastrowid)
    return cur.lastrowid


def cambiar_clave(con, id_administrador: int, clave_nueva: str, ahora: int, actor_id: int) -> None:
    """Cada quien cambia su propia clave. El superusuario puede restablecer la de un administrador; nadie, la suya."""
    adm = con.execute("SELECT usuario, rol FROM administrador WHERE id = ?", (id_administrador,)).fetchone()
    if adm is None:
        raise ErrorNegocio("no-existe", "No existe ese administrador.", 404)
    if actor_id != id_administrador and _rol_de(con, actor_id) != "superusuario":
        raise ErrorNegocio("sin-permiso", "Solo el superusuario puede cambiar la contraseña de otra persona.", 403)
    validar_clave(clave_nueva, adm["usuario"])
    with transaccion(con):
        con.execute("UPDATE administrador SET clave_hash = ?, intentos_fallidos = 0, bloqueado_hasta_ts = NULL WHERE id = ?",
                    (hash_clave(clave_nueva), id_administrador))
        con.execute("DELETE FROM sesion WHERE id_administrador = ?", (id_administrador,))  # cierra sus sesiones abiertas
        bitacora(con, ahora, "administrador", actor_id, "cambiar-clave", "administrador", id_administrador)


def desactivar_administrador(con, id_administrador: int, ahora: int, actor_id: int) -> None:
    """Solo el superusuario desactiva cuentas, y nunca la suya: así nadie puede sacar a los demás para quedarse con el control."""
    if _rol_de(con, actor_id) != "superusuario":
        raise ErrorNegocio("sin-permiso", "Solo el superusuario puede desactivar administradores.", 403)
    if _rol_de(con, id_administrador) == "superusuario":
        raise ErrorNegocio("superusuario-protegido", "El superusuario no se puede desactivar.", 403)
    activos = con.execute("SELECT COUNT(*) c FROM administrador WHERE activo = 1 AND rol = 'administrador'").fetchone()["c"]
    objetivo = con.execute("SELECT activo FROM administrador WHERE id = ?", (id_administrador,)).fetchone()
    if objetivo is None:
        raise ErrorNegocio("no-existe", "No existe ese administrador.", 404)
    if objetivo["activo"] and activos <= 1:
        raise ErrorNegocio("ultimo-admin", "No se puede desactivar al único administrador activo.", 409)
    with transaccion(con):
        con.execute("UPDATE administrador SET activo = 0 WHERE id = ?", (id_administrador,))
        con.execute("DELETE FROM sesion WHERE id_administrador = ?", (id_administrador,))
        bitacora(con, ahora, "administrador", actor_id, "desactivar-administrador", "administrador", id_administrador)


def _nuevo_token(con, id_administrador: int, ahora: int) -> str:
    token = secrets.token_urlsafe(32)
    con.execute("INSERT INTO sesion (token_hash, id_administrador, creada_ts, ultimo_uso_ts) VALUES (?,?,?,?)",
                (hashlib.sha256(token.encode()).hexdigest(), id_administrador, ahora, ahora))
    return token


def iniciar_sesion(con, usuario: str, clave: str, ahora: int) -> str:
    adm = con.execute("SELECT * FROM administrador WHERE usuario = ?", (usuario.strip(),)).fetchone()
    # Mismo mensaje para usuario inexistente y clave mala: no revela qué usuarios existen
    malo = ErrorNegocio("credenciales", "Usuario o contraseña incorrectos.", 401)
    if adm is None or not adm["activo"]:
        hash_clave(clave)  # gasta el mismo tiempo
        raise malo
    if adm["bloqueado_hasta_ts"] and ahora < adm["bloqueado_hasta_ts"]:
        raise ErrorNegocio("bloqueado", "Demasiados intentos. Espera unos minutos e inténtalo de nuevo.", 429)
    if not verificar_clave(clave, adm["clave_hash"]):
        fallos = adm["intentos_fallidos"] + 1
        bloqueo = ahora + BLOQUEO_MS if fallos >= MAX_INTENTOS else None
        with transaccion(con):
            con.execute("UPDATE administrador SET intentos_fallidos = ?, bloqueado_hasta_ts = ? WHERE id = ?",
                        (0 if bloqueo else fallos, bloqueo, adm["id"]))
            bitacora(con, ahora, "sistema", None, "login-fallido", "administrador", adm["id"])
        raise malo
    return abrir_sesion(con, adm["id"], ahora)


def abrir_sesion(con, id_administrador: int, ahora: int) -> str:
    """Abre sesión de un administrador ya verificado (por clave o por huella)."""
    with transaccion(con):
        con.execute("UPDATE administrador SET intentos_fallidos = 0, bloqueado_hasta_ts = NULL WHERE id = ?", (id_administrador,))
        token = _nuevo_token(con, id_administrador, ahora)
        bitacora(con, ahora, "administrador", id_administrador, "login", "administrador", id_administrador)
    return token


def administrador_de_sesion(con, token: str | None, ahora: int):
    """Devuelve la fila del administrador dueño de la sesión, o None si no hay sesión válida."""
    if not token:
        return None
    h = hashlib.sha256(token.encode()).hexdigest()
    s = con.execute("SELECT * FROM sesion WHERE token_hash = ?", (h,)).fetchone()
    if s is None:
        return None
    if ahora - s["ultimo_uso_ts"] > INACTIVIDAD_MS or ahora - s["creada_ts"] > DURACION_MAX_MS:
        con.execute("DELETE FROM sesion WHERE token_hash = ?", (h,))
        return None
    adm = con.execute("SELECT * FROM administrador WHERE id = ? AND activo = 1", (s["id_administrador"],)).fetchone()
    if adm is None:
        return None
    con.execute("UPDATE sesion SET ultimo_uso_ts = ? WHERE token_hash = ?", (ahora, h))
    return adm


def cerrar_sesion(con, token: str | None) -> None:
    if token:
        con.execute("DELETE FROM sesion WHERE token_hash = ?", (hashlib.sha256(token.encode()).hexdigest(),))
