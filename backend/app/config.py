"""Configuración. Los valores de negocio viven en la tabla `configuracion`; aquí solo lo del entorno."""
import os
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Entorno:
    ruta_db: Path
    zona_horaria: str
    simulador: bool  # True = lector simulado y endpoint de pruebas; en producción debe ser False
    host: str


def cargar() -> Entorno:
    return Entorno(
        ruta_db=Path(os.environ.get("TVUAQ_DB", RAIZ.parent / "data" / "tvuaq.db")),
        zona_horaria=os.environ.get("TVUAQ_ZONA", "America/Mexico_City"),
        simulador=os.environ.get("TVUAQ_SIMULADOR", "0") == "1",
        host="127.0.0.1",  # nunca otra cosa: la app solo se atiende desde la propia PC
    )
