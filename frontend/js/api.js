'use strict';
/*
 * Cliente de la API local. Toda lectura y escritura de datos pasa por aquí: el navegador no guarda nada
 * (ni contraseñas ni datos de personas). La sesión del administrador vive en una cookie HttpOnly que el
 * servidor controla; si caduca, cualquier llamada responde 401 y se avisa con el evento `tv:sesion`.
 */
(function (TV) {
  class ErrorApi extends Error {
    constructor(status, codigo, mensaje) {
      super(mensaje);
      this.status = status;
      this.codigo = codigo;
    }
  }

  async function pedir(metodo, url, cuerpo, opciones = {}) {
    let resp;
    try {
      resp = await fetch(url, {
        method: metodo,
        headers: cuerpo !== undefined ? { 'Content-Type': 'application/json' } : undefined,
        body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
        signal: opciones.signal,
      });
    } catch (e) {
      if (e.name === 'AbortError') throw e;
      throw new ErrorApi(0, 'sin-conexion', 'No hay conexión con el sistema. Revisa que el servidor esté en marcha.');
    }
    const datos = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      if (resp.status === 401 && !opciones.sinAvisoSesion) window.dispatchEvent(new CustomEvent('tv:sesion'));
      throw new ErrorApi(resp.status, datos.codigo || 'error', datos.mensaje || 'No se pudo completar la operación.');
    }
    return datos;
  }

  const api = {
    get: (url, o) => pedir('GET', url, undefined, o),
    post: (url, cuerpo = {}, o) => pedir('POST', url, cuerpo, o),
    put: (url, cuerpo, o) => pedir('PUT', url, cuerpo, o),
    del: (url, o) => pedir('DELETE', url, undefined, o),
  };

  // Trae todo lo que necesita la administración y se alinea con la hora del servidor
  async function cargarDatos() {
    const [datos, hora] = await Promise.all([api.get('/api/admin/datos'), api.get('/api/kiosko/hora')]);
    TV.sincronizarHora(hora.ts);
    TV.db.cargar(datos);
  }

  TV.api = api;
  TV.ErrorApi = ErrorApi;
  TV.cargarDatos = cargarDatos;
})(window.TV);
