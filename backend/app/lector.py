"""Lector de huellas detrás de una interfaz común.

Hoy solo existe el simulador (desarrollo en Mac). Cuando haya SDK del DigitalPersona U.are.U 4500 se agrega
`LectorDigitalPersona` en la PC con Windows, con la misma interfaz; el resto de la app no cambia.

Una lectura entrega una `Persona`: ("operador", id) · ("administrador", id) · None (huella no reconocida).
La identificación solo considera operadores ACTIVOS y administradores activos.
"""
from typing import Callable, Optional, Protocol

Persona = Optional[tuple[str, int]]


class Lector(Protocol):
    def suscribir(self, callback: Callable[[Persona], None]) -> None: ...


class LectorSimulado:
    """Sustituto del sensor para desarrollo y pruebas: `poner_dedo` hace lo mismo que un dedo real."""

    def __init__(self) -> None:
        self._callbacks: list[Callable[[Persona], None]] = []

    def suscribir(self, callback: Callable[[Persona], None]) -> None:
        self._callbacks.append(callback)

    def poner_dedo(self, persona: Persona) -> None:
        for cb in list(self._callbacks):
            cb(persona)
