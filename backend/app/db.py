"""Conexión SQLite pensada para apagones: WAL + sincronización completa + llaves foráneas."""
import sqlite3
from pathlib import Path

from .config import RAIZ

SCHEMA = RAIZ / "schema.sql"


def conectar(ruta: Path | str) -> sqlite3.Connection:
    if str(ruta) != ":memory:":
        Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(ruta), check_same_thread=False, isolation_level=None)  # transacciones explícitas
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")
    if str(ruta) != ":memory:":
        con.execute("PRAGMA journal_mode = WAL")
    con.execute("PRAGMA synchronous = FULL")  # cada commit llega al disco aunque se vaya la luz
    return con


# Columnas agregadas después de la primera versión: las bases ya creadas las reciben al arrancar
MIGRACIONES = [
    ("administrador", "rol", "TEXT NOT NULL DEFAULT 'administrador' CHECK (rol IN ('administrador', 'superusuario'))"),
    ("administrador", "id_operador", "INTEGER REFERENCES operador (id) ON DELETE RESTRICT"),
]


def iniciar(con: sqlite3.Connection) -> None:
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    for tabla, columna, definicion in MIGRACIONES:
        existentes = {f["name"] for f in con.execute(f"PRAGMA table_info({tabla})")}
        if columna not in existentes:
            con.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")


def config_int(con: sqlite3.Connection, clave: str) -> int:
    fila = con.execute("SELECT valor FROM configuracion WHERE clave = ?", (clave,)).fetchone()
    return int(fila["valor"])


class transaccion:
    """with transaccion(con): ... → BEGIN IMMEDIATE / COMMIT, o ROLLBACK si falla."""

    def __init__(self, con: sqlite3.Connection):
        self.con = con

    def __enter__(self):
        self.con.execute("BEGIN IMMEDIATE")
        return self.con

    def __exit__(self, tipo, valor, tb):
        self.con.execute("ROLLBACK" if tipo else "COMMIT")
        return False
