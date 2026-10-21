"""Crea el PRIMER administrador (o uno de rescate) desde la consola de la propia PC.

    python -m app.crear_admin            crea un administrador (o restablece la clave de uno existente)
    python -m app.crear_admin --super    crea el SUPERUSUARIO: cuenta de respaldo del equipo desarrollador

El superusuario no se puede crear ni desactivar desde la pantalla: solo desde aquí. Es la garantía de que ningún
administrador pueda quedarse con el control del sistema (ni sacar a los demás).

No hay usuario por defecto: en producción no existe admin/admin. Quien puede ejecutar esto ya tiene acceso
físico y cuenta de Windows en la PC, que es la garantía de recuperación si falla el sensor o se olvida la clave.
"""
import getpass
import sys
import time

from . import config, db, seguridad


def main() -> int:
    con = db.conectar(config.cargar().ruta_db)
    db.iniciar(con)
    usuario = input("Usuario: ").strip()
    nombre = input("Nombre completo: ").strip()
    clave = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
    if clave != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden.")
        return 1
    existe = con.execute("SELECT id FROM administrador WHERE usuario = ?", (usuario,)).fetchone()
    ahora = time.time_ns() // 1_000_000
    try:
        if existe:   # rescate: restablece la clave de un administrador existente
            seguridad.cambiar_clave(con, existe["id"], clave, ahora, existe["id"])
            seguridad.bitacora(con, ahora, "sistema", None, "rescate-clave", "administrador", existe["id"], "desde consola")
            print("Contraseña restablecida.")
        else:
            rol = "superusuario" if "--super" in sys.argv else "administrador"
            seguridad.crear_administrador(con, usuario, nombre, clave, ahora, rol=rol)
            print("Superusuario creado." if rol == "superusuario" else "Administrador creado.")
    except seguridad.ErrorNegocio as e:
        print(e.mensaje)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
