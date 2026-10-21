"""API: permisos. Lo importante: nada administrativo es alcanzable sin sesión de administrador."""
import threading
import time

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app import config, db, seguridad
from app.lector import LectorSimulado
from app.main import crear_app

from conftest import ts

CLAVE = "clave-segura-1"


@pytest.fixture
def ctx(tmp_path):
    entorno = config.Entorno(ruta_db=tmp_path / "t.db", zona_horaria="America/Mexico_City", simulador=True, host="127.0.0.1")
    con = db.conectar(":memory:")
    db.iniciar(con)
    lector = LectorSimulado()
    reloj = {"t": ts("2026-10-19", "06:58")}
    app = crear_app(entorno, con=con, lector=lector, reloj=lambda: reloj["t"])
    seguridad.crear_administrador(con, "ana.admin", "Ana Admin", CLAVE, reloj["t"])
    return app, con, lector, reloj


def rutas_api(app):
    """Todas las rutas de la app, también las de routers incluidos (FastAPI nuevo las envuelve)."""
    out = []
    for r in app.routes:
        sub = getattr(r, "original_router", None)
        out += [x for x in (sub.routes if sub else [r]) if isinstance(x, APIRoute)]
    return out


def cliente(app):
    return TestClient(app, base_url="http://localhost")


def con_sesion(app):
    c = cliente(app)
    assert c.post("/api/auth/login", json={"usuario": "ana.admin", "clave": CLAVE}).status_code == 200
    return c


def test_toda_ruta_admin_exige_sesion(ctx):
    app = ctx[0]
    rutas = [r for r in rutas_api(app) if r.path.startswith("/api/admin")]
    assert len(rutas) > 15
    c = cliente(app)
    for r in rutas:
        for metodo in r.methods - {"HEAD", "OPTIONS"}:
            path = r.path.replace("{id_op}", "1").replace("{id_adm}", "1")
            resp = c.request(metodo, path, json={} if metodo != "GET" else None)
            assert resp.status_code == 401, f"{metodo} {r.path} respondió {resp.status_code} sin sesión"


def test_login_por_huella_solo_acepta_administradores(ctx):
    """La huella de un operador no abre sesión; la de un administrador sí."""
    app, con, lector, _ = ctx
    con.execute("INSERT INTO operador (nombres, ap_paterno, nacimiento, expediente, alta_fecha) VALUES ('A','B','2000-01-01','1','2026-10-01')")
    resultado = {}
    with cliente(app) as c:
        def esperar():
            resultado["r"] = c.post("/api/auth/huella")
        hilo = threading.Thread(target=esperar)
        hilo.start()
        time.sleep(0.5)
        lector.poner_dedo(("operador", 1))
        lector.poner_dedo(None)
        time.sleep(0.3)
        assert "r" not in resultado                                   # sigue esperando: nada abrió sesión
        lector.poner_dedo(("administrador", 1))
        hilo.join(5)
        assert resultado["r"].status_code == 200
        assert c.get("/api/auth/yo").json()["usuario"] == "ana.admin"


def test_login_y_cookie_httponly_strict(ctx):
    c = cliente(ctx[0])
    r = c.post("/api/auth/login", json={"usuario": "ana.admin", "clave": CLAVE})
    cab = r.headers["set-cookie"].lower()
    assert "httponly" in cab and "samesite=strict" in cab
    assert c.get("/api/auth/yo").json()["usuario"] == "ana.admin"
    c.post("/api/auth/logout")
    assert c.get("/api/auth/yo").status_code == 401


def test_clave_incorrecta(ctx):
    r = cliente(ctx[0]).post("/api/auth/login", json={"usuario": "ana.admin", "clave": "mal"})
    assert r.status_code == 401 and r.json()["codigo"] == "credenciales"


def test_no_se_atiende_host_ni_origen_ajenos(ctx):
    c = cliente(ctx[0])
    assert c.get("/api/kiosko/tipos-incidencia", headers={"host": "evil.example"}).status_code == 403
    assert c.post("/api/auth/login", json={"usuario": "x", "clave": "y"}, headers={"origin": "http://evil.example"}).status_code == 403
    assert c.get("/api/kiosko/tipos-incidencia").status_code == 200


def test_el_kiosko_no_acepta_identidad_desde_el_navegador(ctx):
    """Ninguna ruta del kiosko recibe un id de operador para registrar asistencia: la identidad sale del lector."""
    app = ctx[0]
    c = cliente(app)
    for ruta in ("/api/kiosko/entrada", "/api/kiosko/salida", "/api/kiosko/registrar"):
        assert c.post(ruta, json={"id_operador": 1}).status_code in (404, 405)
    rutas = [r for r in rutas_api(app) if r.path.startswith("/api/kiosko")]
    assert rutas and not [r for r in rutas if "{" in r.path]


def test_simulador_solo_existe_si_esta_activado(ctx, tmp_path):
    app2 = crear_app(config.Entorno(ruta_db=tmp_path / "x.db", zona_horaria="America/Mexico_City", simulador=False, host="127.0.0.1"),
                     con=ctx[1], lector=LectorSimulado())
    assert cliente(app2).post("/api/dev/huella", json={}).status_code in (404, 405)


def test_admin_crea_operador_lo_da_de_baja_y_otro_admin(ctx):
    app = ctx[0]
    c = con_sesion(app)
    nuevo = {"nombres": "María", "ap_paterno": "López", "nacimiento": "2001-11-02", "expediente": "279318",
             "horarios": [{"dia_semana": 2, "hora_inicio": "07:00", "hora_fin": "13:00"}]}
    op = c.post("/api/admin/operadores", json=nuevo)
    assert op.status_code == 200
    id_op = op.json()["id"]
    assert c.post("/api/admin/operadores", json=nuevo).status_code == 409           # expediente repetido
    baja = c.post(f"/api/admin/operadores/{id_op}/baja", json={"motivo": "renuncia"}).json()
    assert baja["activo"] is False and baja["dias_para_borrado"] == 30
    assert c.get("/api/admin/operadores").json() == []                              # ocultos por defecto
    assert len(c.get("/api/admin/operadores?inactivos=true").json()) == 1
    assert c.post(f"/api/admin/operadores/{id_op}/reingreso").json()["activo"] is True
    assert c.post("/api/admin/administradores", json={"usuario": "beto", "nombre": "Beto", "clave": "otra-clave-9"}).status_code == 200
    assert c.post("/api/auth/login", json={"usuario": "beto", "clave": "otra-clave-9"}).status_code == 200


def test_flujo_de_huella_por_eventos(ctx):
    app, con, lector, reloj = ctx
    c = con_sesion(app)
    c.post("/api/admin/operadores", json={"nombres": "Juan", "ap_paterno": "Pérez", "nacimiento": "2002-03-14", "expediente": "1",
                                          "horarios": [{"dia_semana": 1, "hora_inicio": "07:00", "hora_fin": "12:00"}]})
    eventos = []
    app.state.suscriptores.append(type("Cola", (), {"put_nowait": lambda self, ev: eventos.append(ev)})())
    with c:   # arranca el ciclo de vida: ahí se conecta el lector
        lector.poner_dedo(("operador", 1))
        for _ in range(40):
            if eventos:
                break
            time.sleep(0.05)
    assert eventos and eventos[0]["evento"] == "entrada" and eventos[0]["llegada"] == "a-tiempo"
