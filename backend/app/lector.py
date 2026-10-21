"""Lector de huellas detrás de una interfaz común.

Hoy solo existe el simulador (desarrollo en Mac). Cuando haya SDK del DigitalPersona U.are.U 4500 se agrega
`LectorDigitalPersona` en la PC con Windows, con la misma interfaz; el resto de la app no cambia.

Una lectura entrega una `Persona`: ("operador", id) · ("administrador", id) · None (huella no reconocida).
La identificación solo considera operadores ACTIVOS y administradores activos.
"""
import secrets
from typing import Callable, Optional, Protocol

Persona = Optional[tuple[str, int]]


class Lector(Protocol):
    def suscribir(self, callback: Callable[[Persona], None]) -> None: ...

    def enrolar(self) -> bytes:
        """Captura una huella nueva y devuelve su plantilla. Sin lector disponible lanza LectorNoDisponible."""
        ...

    def estado(self) -> dict:
        """{'ok': bool, 'detalle': str}. Se consulta seguido: si el lector deja de responder (por ejemplo tras una
        actualización de driver) la pantalla lo avisa en vez de quedarse esperando en silencio."""
        ...


class LectorNoDisponible(Exception):
    pass


class LectorSimulado:
    """Sustituto del sensor para desarrollo y pruebas: `poner_dedo` hace lo mismo que un dedo real."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[[Persona], None]] = []
        self._falla = False

    def estado(self) -> dict:
        return {"ok": False, "detalle": "El lector no responde"} if self._falla else {"ok": True, "detalle": "Lector listo"}

    def fallar(self, falla: bool) -> None:
        """Solo demostración: simula que el lector deja de responder."""
        self._falla = falla

    def suscribir(self, callback: Callable[[Persona], None]) -> None:
        self._callbacks.append(callback)

    def enrolar(self) -> bytes:
        return secrets.token_bytes(64)   # plantilla ficticia: el simulador identifica por id, no por la imagen

    def poner_dedo(self, persona: Persona) -> None:
        for cb in list(self._callbacks):
            cb(persona)
