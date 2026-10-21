"""Respaldos de la base: copia consistente, verificada, rotada y con aviso cuando falta.

Se copia con la API de respaldo de SQLite (nunca copiando el archivo a mano: con WAL activo eso puede dejar una copia
corrupta). Cada copia se abre y se verifica (`integrity_check`) y se le calcula su huella SHA-256.

Destinos: `local` (carpeta en la PC) y `usb` (memoria USB). Si la USB no está conectada no falla nada: se avisa.
Retención corta a propósito (7 diarios + 4 semanales, ~4 semanas): como el sistema borra TODO de un operador a los
30 días de su baja, los respaldos no deben guardar esos datos por meses.
"""
import hashlib
import shutil
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .db import transaccion
from .seguridad import bitacora

DIARIOS = 7
SEMANALES = 4
HORAS_ALERTA = {"local": 30, "usb": 72}   # sin respaldo bueno en este tiempo → alerta en pantalla
PREFIJO = "tvuaq-"


def _sha256(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def _integra(ruta: Path) -> bool:
    try:
        c = sqlite3.connect(f"file:{ruta}?mode=ro", uri=True)
        try:
            return c.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            c.close()
    except sqlite3.DatabaseError:
        return False


def crear_copia(con: sqlite3.Connection, carpeta: Path, ahora_ms: int, zona: ZoneInfo) -> dict:
    """Copia la base a `carpeta`, la verifica y devuelve {archivo, bytes, sha256}. Lanza si la copia no es íntegra."""
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{PREFIJO}{datetime.fromtimestamp(ahora_ms / 1000, zona):%Y%m%d-%H%M%S}.db"
    destino, parcial = carpeta / nombre, carpeta / (nombre + ".parcial")
    copia = sqlite3.connect(parcial)
    try:
        con.backup(copia)
    finally:
        copia.close()
    if not _integra(parcial):
        parcial.unlink(missing_ok=True)
        raise RuntimeError("La copia no pasó la verificación de integridad")
    parcial.replace(destino)   # solo aparece con su nombre final cuando ya está completa y verificada
    return {"archivo": destino.name, "bytes": destino.stat().st_size, "sha256": _sha256(destino)}


def rotar(carpeta: Path, zona: ZoneInfo, diarios: int = DIARIOS, semanales: int = SEMANALES) -> list[str]:
    """Conserva la copia más reciente de cada uno de los últimos `diarios` días y de las últimas `semanales` semanas."""
    copias = sorted(carpeta.glob(f"{PREFIJO}*.db"), reverse=True)
    conservar, dias, semanas = set(), {}, {}
    for c in copias:
        try:
            fecha = datetime.strptime(c.name[len(PREFIJO):len(PREFIJO) + 8], "%Y%m%d").date()
        except ValueError:
            conservar.add(c)   # un archivo que no es nuestro no se toca
            continue
        dias.setdefault(fecha, c)
        semanas.setdefault(fecha.isocalendar()[:2], c)
    conservar |= {v for _, v in sorted(dias.items(), reverse=True)[:diarios]}
    conservar |= {v for _, v in sorted(semanas.items(), reverse=True)[:semanales]}
    borradas = []
    for c in copias:
        if c not in conservar:
            c.unlink()
            borradas.append(c.name)
    return borradas


def _destinos(entorno) -> list[tuple[str, Path | None]]:
    return [("local", entorno.respaldo_local), ("usb", entorno.respaldo_usb)]


def _disponible(carpeta: Path | None) -> bool:
    """La carpeta de destino sirve si ya existe o si existe su carpeta madre (la unidad de la USB está conectada)."""
    return carpeta is not None and (carpeta.exists() or carpeta.parent.exists())


def respaldar_todo(con, entorno, ahora_ms: int, zona: ZoneInfo, actor: tuple[str, int | None] = ("sistema", None)) -> list[dict]:
    """Respalda en todos los destinos configurados. Nunca lanza: cada resultado trae ok/motivo."""
    resultados = []
    for nombre, carpeta in _destinos(entorno):
        if carpeta is None:
            resultados.append({"destino": nombre, "ok": False, "configurado": False, "detalle": "No configurado"})
            continue
        if not _disponible(carpeta):
            r = {"destino": nombre, "ok": False, "configurado": True, "detalle": "No disponible (¿memoria USB desconectada?)"}
        else:
            try:
                info = crear_copia(con, carpeta, ahora_ms, zona)
                rotar(carpeta, zona)
                r = {"destino": nombre, "ok": True, "configurado": True, "detalle": "Respaldo verificado", **info}
            except Exception as e:   # noqa: BLE001 - un destino que falla no debe impedir el otro
                r = {"destino": nombre, "ok": False, "configurado": True, "detalle": f"Falló: {type(e).__name__}: {e}"}
        with transaccion(con):
            con.execute("INSERT INTO respaldo (ts, destino, archivo, bytes, sha256, ok, detalle) VALUES (?,?,?,?,?,?,?)",
                        (ahora_ms, nombre, r.get("archivo", ""), r.get("bytes", 0), r.get("sha256", ""), int(r["ok"]), r["detalle"]))
            bitacora(con, ahora_ms, actor[0], actor[1], "respaldo-ok" if r["ok"] else "respaldo-fallido", detalle=f"{nombre}: {r['detalle'][:120]}")
        resultados.append(r)
    return resultados


def estado(con, entorno, ahora_ms: int) -> dict:
    """Qué tan al día están los respaldos de cada destino (para la pantalla de administración)."""
    destinos = []
    for nombre, carpeta in _destinos(entorno):
        ultimo = con.execute("SELECT ts, archivo, bytes FROM respaldo WHERE destino = ? AND ok = 1 ORDER BY ts DESC LIMIT 1", (nombre,)).fetchone()
        edad_h = (ahora_ms - ultimo["ts"]) / 3_600_000 if ultimo else None
        configurado = carpeta is not None
        alerta = ""
        if not configurado:
            alerta = "Sin memoria USB configurada" if nombre == "usb" else "Sin carpeta de respaldo"
        elif ultimo is None:
            alerta = "Aún no hay ningún respaldo"
        elif edad_h > HORAS_ALERTA[nombre]:
            alerta = f"Último respaldo hace {int(edad_h // 24)} días" if edad_h >= 48 else f"Último respaldo hace {int(edad_h)} horas"
        destinos.append({"destino": nombre, "configurado": configurado, "disponible": _disponible(carpeta),
                         "ultimo_ts": ultimo["ts"] if ultimo else None, "ultimo_archivo": ultimo["archivo"] if ultimo else None,
                         "bytes": ultimo["bytes"] if ultimo else None, "alerta": alerta})
    historial = [dict(f) for f in con.execute("SELECT ts, destino, archivo, bytes, ok, detalle FROM respaldo ORDER BY ts DESC, id DESC LIMIT 12")]
    return {"destinos": destinos, "historial": historial}


def debe_respaldar(con, ahora_ms: int, zona: ZoneInfo, hora_local: int = 2, cada_horas: int = 20) -> bool:
    """Un respaldo diario: de madrugada, o al arrancar si ya pasó más de un día. Los fallidos se reintentan cada hora."""
    ultimo = con.execute("SELECT ts, ok FROM respaldo ORDER BY ts DESC LIMIT 1").fetchone()
    if ultimo is None:
        return True
    edad_h = (ahora_ms - ultimo["ts"]) / 3_600_000
    if not ultimo["ok"]:
        return edad_h >= 1
    ahora = datetime.fromtimestamp(ahora_ms / 1000, zona)
    return edad_h >= cada_horas and (ahora.hour >= hora_local or edad_h >= 26)


def restaurar(archivo: Path, ruta_db: Path) -> Path:
    """Reemplaza la base por un respaldo. El servidor debe estar APAGADO. La base anterior se conserva aparte."""
    archivo, ruta_db = Path(archivo), Path(ruta_db)
    if not archivo.exists() or not _integra(archivo):
        raise ValueError("El respaldo no existe o no pasó la verificación de integridad; no se restauró nada.")
    previa = None
    if ruta_db.exists():
        previa = ruta_db.with_name(ruta_db.name + f".antes-de-restaurar-{datetime.now():%Y%m%d-%H%M%S}")
        shutil.move(str(ruta_db), previa)
    for sufijo in ("-wal", "-shm"):
        ruta_db.with_name(ruta_db.name + sufijo).unlink(missing_ok=True)
    shutil.copy2(archivo, ruta_db)
    return previa
