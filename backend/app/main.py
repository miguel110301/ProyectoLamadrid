"""API local de Control Maestro TvUAQ.

Dos mundos separados:
  /api/kiosko/*  pantalla operativa. Sin sesión, pero NUNCA recibe "quién soy" desde el navegador:
                 la identidad sale del lector de huellas. Solo permite entrada/salida e incidencias.
  /api/admin/*   administración. TODAS sus rutas cuelgan de un router con `requiere_admin`, así que una ruta
                 nueva no puede quedar abierta por olvido (hay una prueba que lo verifica).
Además: solo se atiende a la propia PC (127.0.0.1) y se rechazan Host/Origin ajenos.
"""
import asyncio
import contextlib
import json
import time
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, db, operadores, reglas, seguridad
from .kiosko import Kiosko
from .lector import Lector, LectorSimulado
from .seguridad import ErrorNegocio

COOKIE = "tvuaq_sesion"
LOCALES = {"127.0.0.1", "localhost", "[::1]", "::1", "testserver"}
FRONTEND = config.RAIZ.parent / "frontend"
ESPERA_HUELLA_ADMIN_S = 30


def _ms() -> int:
    return time.time_ns() // 1_000_000


# ---------- cuerpos de petición ----------
class Login(BaseModel):
    usuario: str
    clave: str


class Turno(BaseModel):
    dia_semana: int = Field(ge=0, le=6)
    hora_inicio: str
    hora_fin: str


class OperadorNuevo(BaseModel):
    nombres: str
    ap_paterno: str
    ap_materno: str = ""
    nacimiento: str
    expediente: str
    carrera: str = ""
    horarios: list[Turno]


class CambioHorario(BaseModel):
    desde_fecha: str
    horarios: list[Turno]


class Baja(BaseModel):
    motivo: str


class TurnoRef(BaseModel):
    fecha: str
    id_horario: int


class Justificacion(TurnoRef):
    motivo: str


class Edicion(TurnoRef):
    estado: str
    motivo: str = ""


class AdminNuevo(BaseModel):
    usuario: str
    nombre: str
    clave: str


class ClaveNueva(BaseModel):
    clave: str


class Incidencia(BaseModel):
    tipo: str
    hora: str
    programa: str = ""
    duracion_min: int | None = None
    observacion: str


class Confirmacion(BaseModel):
    aceptar: bool


class DedoSimulado(BaseModel):
    tipo: str | None = None   # 'operador' | 'administrador' | None (no reconocida)
    id: int | None = None


def crear_app(entorno: config.Entorno | None = None, con=None, lector: Lector | None = None, reloj=_ms, mono=time.monotonic) -> FastAPI:
    entorno = entorno or config.cargar()
    zona = ZoneInfo(entorno.zona_horaria)

    @contextlib.asynccontextmanager
    async def ciclo(app: FastAPI):
        loop = asyncio.get_running_loop()
        app.state.lector.suscribir(lambda persona: loop.call_soon_threadsafe(manejar_lectura, persona))
        tareas = [asyncio.create_task(_vigilar_reloj(app)), asyncio.create_task(_mantenimiento(app))]
        yield
        for t in tareas:
            t.cancel()

    app = FastAPI(title="Control Maestro TvUAQ", docs_url=None, redoc_url=None, openapi_url=None, lifespan=ciclo)
    if con is None:
        con = db.conectar(entorno.ruta_db)
        db.iniciar(con)
    app.state.con, app.state.zona, app.state.reloj = con, zona, reloj
    app.state.kiosko = Kiosko(con, zona, reloj=reloj, mono=mono)
    app.state.lector = lector or LectorSimulado()
    app.state.suscriptores: list[asyncio.Queue] = []
    app.state.esperando_admin: list[asyncio.Future] = []

    def publicar(evento: dict) -> None:
        for q in app.state.suscriptores:
            q.put_nowait(evento)

    def manejar_lectura(persona) -> None:
        """Una huella llegó del lector. Si un administrador la esperaba para iniciar sesión, la usa; si no, es del kiosko."""
        try:
            if persona and persona[0] == "administrador" and app.state.esperando_admin:
                adm = app.state.con.execute("SELECT id FROM administrador WHERE id = ? AND activo = 1", (persona[1],)).fetchone()
                if adm:
                    for f in app.state.esperando_admin:
                        if not f.done():
                            f.set_result(adm["id"])
                    return
            publicar(app.state.kiosko.procesar(persona))
        except ErrorNegocio as e:
            publicar({"evento": "error", "codigo": e.codigo, "mensaje": e.mensaje})

    # ---------- protección general ----------
    @app.middleware("http")
    async def solo_local(request: Request, llamada):
        crudo = request.headers.get("host") or ""
        host = crudo.split("]")[0] + "]" if crudo.startswith("[") else crudo.split(":")[0]
        origen = request.headers.get("origin")
        origen_host = (urlparse(origen).hostname or "") if origen else None
        cliente = request.client.host if request.client else ""
        if cliente not in ("127.0.0.1", "::1", "testclient") or host not in LOCALES or (origen_host and origen_host not in LOCALES):
            return JSONResponse({"codigo": "prohibido", "mensaje": "Acceso no permitido."}, status_code=403)
        return await llamada(request)

    @app.exception_handler(ErrorNegocio)
    async def error_negocio(_, e: ErrorNegocio):
        return JSONResponse({"codigo": e.codigo, "mensaje": e.mensaje}, status_code=e.http)

    def requiere_admin(request: Request):
        adm = seguridad.administrador_de_sesion(app.state.con, request.cookies.get(COOKIE), app.state.reloj())
        if adm is None:
            raise ErrorNegocio("no-autenticado", "Inicia sesión como administrador.", 401)
        return adm

    def poner_cookie(resp: Response, token: str) -> None:
        resp.set_cookie(COOKIE, token, httponly=True, samesite="strict", path="/", max_age=seguridad.DURACION_MAX_MS // 1000)

    # ---------- autenticación ----------
    auth = APIRouter(prefix="/api/auth")

    @auth.post("/login")
    async def login(datos: Login, resp: Response):
        poner_cookie(resp, seguridad.iniciar_sesion(app.state.con, datos.usuario, datos.clave, app.state.reloj()))
        return {"ok": True}

    @auth.post("/huella")
    async def login_huella(resp: Response):
        """Espera hasta 30 s a que un administrador ponga su huella en el lector."""
        futuro = asyncio.get_running_loop().create_future()
        app.state.esperando_admin.append(futuro)
        try:
            id_adm = await asyncio.wait_for(futuro, ESPERA_HUELLA_ADMIN_S)
        except asyncio.TimeoutError:
            raise ErrorNegocio("sin-huella", "No se recibió la huella del administrador.", 408)
        finally:
            app.state.esperando_admin.remove(futuro)
        poner_cookie(resp, seguridad.abrir_sesion(app.state.con, id_adm, app.state.reloj()))
        return {"ok": True}

    @auth.post("/logout")
    async def logout(request: Request, resp: Response):
        seguridad.cerrar_sesion(app.state.con, request.cookies.get(COOKIE))
        resp.delete_cookie(COOKIE, path="/")
        return {"ok": True}

    @auth.get("/yo")
    async def yo(adm=Depends(requiere_admin)):
        return {"id": adm["id"], "usuario": adm["usuario"], "nombre": adm["nombre"]}

    # ---------- kiosko (operadores) ----------
    kiosko = APIRouter(prefix="/api/kiosko")

    @kiosko.get("/eventos")
    async def eventos(request: Request):
        cola: asyncio.Queue = asyncio.Queue()
        app.state.suscriptores.append(cola)

        async def flujo():
            try:
                yield "retry: 2000\n\n"      # si se cae la conexión, el navegador reconecta solo
                while not await request.is_disconnected():
                    try:
                        ev = await asyncio.wait_for(cola.get(), 15)
                        yield f"data: {json.dumps(ev, ensure_ascii=False)}\n\n"
                    except asyncio.TimeoutError:
                        yield ": latido\n\n"
            finally:
                app.state.suscriptores.remove(cola)

        return StreamingResponse(flujo(), media_type="text/event-stream", headers={"Cache-Control": "no-store"})

    @kiosko.get("/tipos-incidencia")
    async def tipos():
        return [dict(f) for f in app.state.con.execute("SELECT id, nombre, requiere_duracion FROM tipo_incidencia")]

    @kiosko.get("/en-turno")
    async def en_turno():
        """Quién tiene entrada abierta ahora (solo nombres, para la pantalla)."""
        ahora, cfg = app.state.reloj(), reglas.Cfg.desde_db(app.state.con)
        out = []
        for o in app.state.con.execute("SELECT id, nombres, ap_paterno FROM operador WHERE activo = 1"):
            v = reglas.registro_vigente(app.state.con, o["id"], ahora, cfg, zona)
            if v:
                out.append({"nombre": f"{o['nombres']} {o['ap_paterno']}", "entrada_ts": v[0]["entrada_ts"], "fin": v[1]["fin"]})
        return out

    @kiosko.post("/incidencia")
    async def incidencia(datos: Incidencia):
        app.state.kiosko.preparar_incidencia(datos.model_dump())
        return {"esperando_huella": True}

    @kiosko.delete("/incidencia")
    async def cancelar_incidencia():
        app.state.kiosko.cancelar_incidencia()
        return {"ok": True}

    @kiosko.post("/confirmar-salida")
    async def confirmar_salida(datos: Confirmacion):
        return app.state.kiosko.confirmar_salida(datos.aceptar)

    # ---------- administración (todo exige administrador) ----------
    admin = APIRouter(prefix="/api/admin", dependencies=[Depends(requiere_admin)])

    def _operador_json(o) -> dict:
        c, ahora = app.state.con, app.state.reloj()
        return {"id": o["id"], "nombres": o["nombres"], "ap_paterno": o["ap_paterno"], "ap_materno": o["ap_materno"],
                "nacimiento": o["nacimiento"], "expediente": o["expediente"], "carrera": o["carrera"], "activo": bool(o["activo"]),
                "huella": c.execute("SELECT 1 FROM huella WHERE id_operador = ?", (o["id"],)).fetchone() is not None,
                "dias_para_borrado": operadores.dias_restantes_purga(c, o["id"], ahora),
                "horarios": [dict(h) for h in c.execute(
                    "SELECT id, dia_semana, hora_inicio, hora_fin, vigente_desde, vigente_hasta FROM horario WHERE id_operador = ? AND vigente_hasta IS NULL", (o["id"],))]}

    def _op(id_op: int):
        o = app.state.con.execute("SELECT * FROM operador WHERE id = ?", (id_op,)).fetchone()
        if o is None:
            raise ErrorNegocio("no-existe", "No existe ese operador.", 404)
        return o

    @admin.get("/operadores")
    async def listar_operadores(inactivos: bool = False):
        filas = app.state.con.execute("SELECT * FROM operador WHERE activo = 1 OR ? ORDER BY ap_paterno, nombres", (int(inactivos),))
        return [_operador_json(o) for o in filas]

    @admin.post("/operadores")
    async def alta(datos: OperadorNuevo, adm=Depends(requiere_admin)):
        d = datos.model_dump()
        id_op = operadores.alta_operador(app.state.con, d, d.pop("horarios"), adm["id"], app.state.reloj(), zona)
        return _operador_json(_op(id_op))

    @admin.put("/operadores/{id_op}/horario")
    async def horario(id_op: int, datos: CambioHorario, adm=Depends(requiere_admin)):
        _op(id_op)
        operadores.cambiar_horario(app.state.con, id_op, [t.model_dump() for t in datos.horarios], datos.desde_fecha, adm["id"], app.state.reloj())
        return _operador_json(_op(id_op))

    @admin.post("/operadores/{id_op}/baja")
    async def baja(id_op: int, datos: Baja, adm=Depends(requiere_admin)):
        operadores.dar_de_baja(app.state.con, id_op, datos.motivo, adm["id"], app.state.reloj())
        return _operador_json(_op(id_op))

    @admin.post("/operadores/{id_op}/reingreso")
    async def reingreso(id_op: int, adm=Depends(requiere_admin)):
        operadores.reingresar(app.state.con, id_op, adm["id"], app.state.reloj())
        return _operador_json(_op(id_op))

    @admin.get("/asistencia")
    async def asistencia(desde: str, hasta: str, id_operador: int | None = None, pendientes: bool = False):
        """Resumen por operador (tabla de asistencias, pase de lista y reporte individual)."""
        ahora, cfg = app.state.reloj(), reglas.Cfg.desde_db(app.state.con)
        ids = [id_operador] if id_operador else [f["id"] for f in app.state.con.execute("SELECT id FROM operador ORDER BY ap_paterno, nombres")]
        return [{"id_operador": i, **reglas.resumen(app.state.con, i, desde, hasta, ahora, cfg, zona, pendientes)} for i in ids]

    @admin.post("/operadores/{id_op}/justificar")
    async def justificar(id_op: int, datos: Justificacion, adm=Depends(requiere_admin)):
        operadores.justificar(app.state.con, id_op, datos.fecha, datos.id_horario, datos.motivo, adm["id"], app.state.reloj(), zona)
        return {"ok": True}

    @admin.post("/operadores/{id_op}/quitar-justificacion")
    async def quitar_justificacion(id_op: int, datos: TurnoRef, adm=Depends(requiere_admin)):
        operadores.quitar_justificacion(app.state.con, id_op, datos.fecha, datos.id_horario, adm["id"], app.state.reloj())
        return {"ok": True}

    @admin.post("/operadores/{id_op}/editar-estatus")
    async def editar(id_op: int, datos: Edicion, adm=Depends(requiere_admin)):
        operadores.editar_estatus(app.state.con, id_op, datos.fecha, datos.id_horario, datos.estado, datos.motivo, adm["id"], app.state.reloj(), zona)
        return {"ok": True}

    @admin.post("/operadores/{id_op}/quitar-edicion")
    async def quitar_edicion(id_op: int, datos: TurnoRef, adm=Depends(requiere_admin)):
        operadores.quitar_edicion(app.state.con, id_op, datos.fecha, datos.id_horario, adm["id"], app.state.reloj())
        return {"ok": True}

    @admin.get("/incidencias")
    async def incidencias(desde: str, hasta: str):
        filas = app.state.con.execute(
            """SELECT i.*, t.nombre AS tipo_nombre, o.nombres || ' ' || o.ap_paterno AS operador FROM incidencia i
               JOIN tipo_incidencia t ON t.id = i.id_tipo JOIN operador o ON o.id = i.id_operador
               WHERE i.fecha BETWEEN ? AND ? ORDER BY i.registrado_ts""", (desde, hasta))
        return [dict(f) for f in filas]

    @admin.get("/administradores")
    async def listar_admins():
        return [dict(f) for f in app.state.con.execute("SELECT id, usuario, nombre, activo, creado_ts FROM administrador ORDER BY id")]

    @admin.post("/administradores")
    async def nuevo_admin(datos: AdminNuevo, adm=Depends(requiere_admin)):
        i = seguridad.crear_administrador(app.state.con, datos.usuario, datos.nombre, datos.clave, app.state.reloj(), creado_por=adm["id"])
        return {"id": i}

    @admin.post("/administradores/{id_adm}/desactivar")
    async def desactivar_admin(id_adm: int, adm=Depends(requiere_admin)):
        seguridad.desactivar_administrador(app.state.con, id_adm, app.state.reloj(), adm["id"])
        return {"ok": True}

    @admin.post("/administradores/{id_adm}/clave")
    async def clave_admin(id_adm: int, datos: ClaveNueva, adm=Depends(requiere_admin)):
        seguridad.cambiar_clave(app.state.con, id_adm, datos.clave, app.state.reloj(), adm["id"])
        return {"ok": True}

    @admin.get("/bitacora")
    async def bitacora(limite: int = 200):
        return [dict(f) for f in app.state.con.execute("SELECT * FROM bitacora ORDER BY id DESC LIMIT ?", (min(limite, 1000),))]

    app.include_router(auth)
    app.include_router(kiosko)
    app.include_router(admin)

    # Solo para desarrollo con el lector simulado (nunca disponible en producción)
    if entorno.simulador:
        @app.post("/api/dev/huella")
        async def poner_dedo(datos: DedoSimulado):
            persona = (datos.tipo, datos.id) if datos.tipo else None
            app.state.lector.poner_dedo(persona)
            return {"ok": True}

    if FRONTEND.is_dir():
        app.mount("/", StaticFiles(directory=FRONTEND, html=True), name="frontend")
    return app


# ---------- tareas en segundo plano ----------
async def _vigilar_reloj(app: FastAPI, cada_s: float = 30, umbral_s: float = 5) -> None:
    """Detecta saltos de hora (p. ej. al volver el internet y resincronizar) y los deja en bitácora."""
    pared, mono = app.state.reloj(), time.monotonic()
    while True:
        await asyncio.sleep(cada_s)
        p2, m2 = app.state.reloj(), time.monotonic()
        salto = (p2 - pared) / 1000 - (m2 - mono)
        if abs(salto) > umbral_s:
            seguridad.bitacora(app.state.con, p2, "sistema", None, "salto-reloj", detalle=f"{salto:+.0f} s")
        pared, mono = p2, m2


async def _mantenimiento(app: FastAPI) -> None:
    """Cada hora: purga de bajas vencidas y sesiones caducadas."""
    while True:
        try:
            operadores.purgar(app.state.con, app.state.reloj())
            app.state.con.execute("DELETE FROM sesion WHERE ? - ultimo_uso_ts > ?", (app.state.reloj(), seguridad.INACTIVIDAD_MS))
        except Exception as e:  # nunca debe tumbar el servidor
            seguridad.bitacora(app.state.con, app.state.reloj(), "sistema", None, "error-mantenimiento", detalle=type(e).__name__)
        await asyncio.sleep(3600)


def app_produccion() -> FastAPI:
    return crear_app()
