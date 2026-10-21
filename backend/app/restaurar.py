"""Restaura un respaldo desde la consola de la PC (con el servidor apagado).

    python -m app.restaurar <archivo-de-respaldo.db>
    python -m app.restaurar --lista            muestra los respaldos disponibles
"""
import sys

from . import config, respaldos


def main() -> int:
    entorno = config.cargar()
    if "--lista" in sys.argv or len(sys.argv) < 2:
        for nombre, carpeta in respaldos._destinos(entorno):
            if carpeta and carpeta.exists():
                for c in sorted(carpeta.glob(f"{respaldos.PREFIJO}*.db"), reverse=True):
                    print(f"[{nombre}] {c}")
        print("\nUso: python -m app.restaurar <archivo>   (con el servidor apagado)")
        return 0
    if input("Esto reemplaza la base actual (se guarda una copia aparte). Escribe SI para continuar: ").strip() != "SI":
        print("Cancelado.")
        return 1
    try:
        previa = respaldos.restaurar(sys.argv[1], entorno.ruta_db)
    except ValueError as e:
        print(e)
        return 1
    print("Restaurado." + (f" La base anterior quedó en {previa}" if previa else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
