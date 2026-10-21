'use strict';
/*
 * Lector biométrico. La pantalla siempre espera una huella, pero NO la lee el navegador: el lector está
 * conectado al servidor, que identifica a la persona y avisa por eventos (SSE). Aquí solo se reciben esos
 * avisos ya resueltos (entrada, salida, huella no reconocida…); el navegador nunca dice quién es nadie.
 *
 * Cada pantalla o diálogo que necesite los avisos "empuja" un manejador en una pila: solo el de arriba
 * recibe el evento y, al cerrarse, vuelve a recibirlo el de abajo.
 *
 * Modo demostración (solo si el servidor se inició con el lector simulado): un panel permite "poner el
 * dedo" de alguien y mover la hora del sistema para enseñar a tiempo, retardo, falta o el borrado a los 30 días.
 */
(function (TV) {
  const { esc } = TV.util;
  const pila = [];
  let dock = null;
  let origen = null;
  let estadoConexion = 'conectando';
  const oyentesConexion = [];

  const sensor = {
    empujar(fn) {
      const entrada = { fn };
      pila.push(entrada);
      return () => {
        const i = pila.indexOf(entrada);
        if (i >= 0) pila.splice(i, 1);
      };
    },
    emitir(ev) {
      const tope = pila[pila.length - 1];
      if (tope) tope.fn(ev);
    },

    // Eventos del servidor. EventSource reconecta solo si se cae la conexión.
    conectar() {
      if (origen) return;
      origen = new EventSource('/api/kiosko/eventos');
      origen.onmessage = (m) => {
        try {
          const ev = JSON.parse(m.data);
          if (ev.ts) TV.sincronizarHora(ev.ts);
          sensor.emitir(ev);
        } catch (e) {
          /* mensaje malformado: se ignora */
        }
      };
      const estado = (e) => {
        estadoConexion = e;
        oyentesConexion.forEach((fn) => fn(e));
      };
      origen.onopen = () => estado('conectado');
      origen.onerror = () => estado('desconectado');
    },
    alCambiarConexion(fn) {
      oyentesConexion.push(fn);
      fn(estadoConexion);
    },

    /* ---------- Modo demostración (simulador) ---------- */
    async personas() {
      try {
        return await TV.api.get('/api/dev/personas', { sinAvisoSesion: true });
      } catch (e) {
        return null; // producción: el simulador no existe
      }
    },
    poner: (persona) => TV.api.post('/api/dev/huella', persona ? { tipo: persona.tipo, id: persona.id } : { tipo: null, id: null }),

    // Simulador incrustado en un formulario (p. ej. incidencias)
    async simuladorEnLinea() {
      const personas = await sensor.personas();
      const caja = document.createElement('div');
      if (!personas) return caja;
      const ops = personas.filter((p) => p.tipo === 'operador');
      caja.className = 'sim-linea';
      caja.innerHTML = `
        <span class="sim-linea__rotulo">Simulador de sensor · solo demostración</span>
        <label class="campo"><span class="solo-lectores">Huella de</span>
          <select data-quien>${ops.map((o) => `<option value="${o.id}">${esc(o.nombre)}</option>`).join('')}</select></label>
        <button type="button" class="btn btn--primario btn--chico" data-poner>${TV.ui.icono('huella')} Simular huella</button>
        <button type="button" class="btn btn--secundario btn--chico" data-fallo>No reconocida</button>`;
      const quien = caja.querySelector('[data-quien]');
      caja.querySelector('[data-poner]').addEventListener('click', () => quien.value && sensor.poner({ tipo: 'operador', id: Number(quien.value) }));
      caja.querySelector('[data-fallo]').addEventListener('click', () => sensor.poner(null));
      return caja;
    },

    // El panel flotante se oculta cuando no se necesita (p. ej. dentro de la administración)
    visible(v) {
      if (dock) dock.hidden = !v;
    },

    // Panel flotante. contexto 'admin' agrega a los administradores y el botón de borrado de bajas.
    async montarSimulador(contexto = 'operador') {
      const inicial = await sensor.personas();
      if (!inicial) return;
      dock = document.createElement('details');
      dock.className = 'sim';
      dock.open = contexto !== 'admin'; // en administración empieza plegado para no tapar las tablas
      dock.innerHTML = `
        <summary>Modo demostración · simulador</summary>
        <div class="sim__cuerpo">
          <label class="campo"><span class="campo__etiqueta">Huella de</span><select data-quien></select></label>
          <div class="acciones">
            <button type="button" class="btn btn--primario btn--chico" data-poner>Poner dedo</button>
            <button type="button" class="btn btn--secundario btn--chico" data-fallo>No reconocida</button>
          </div>
          <hr />
          <label class="campo"><span class="campo__etiqueta">Hora del sistema <small data-hora></small></span><input type="datetime-local" data-fecha /></label>
          <div class="acciones">
            <button type="button" class="btn btn--secundario btn--chico" data-aplicar>Aplicar hora</button>
            <button type="button" class="btn btn--texto btn--chico" data-real>Hora real</button>
          </div>
          <div class="acciones">
            <button type="button" class="btn btn--texto btn--chico" data-sumar="5">+5 min</button>
            <button type="button" class="btn btn--texto btn--chico" data-sumar="60">+1 h</button>
            <button type="button" class="btn btn--texto btn--chico" data-sumar="1440">+1 día</button>
            <button type="button" class="btn btn--texto btn--chico" data-sumar="44640">+31 días</button>
          </div>
          ${contexto === 'admin' ? '<button type="button" class="btn btn--secundario btn--chico" data-purgar>Ejecutar borrado de bajas vencidas</button>' : ''}
        </div>`;
      const quien = dock.querySelector('[data-quien]');
      const llenar = async () => {
        const previo = quien.value;
        const todas = (await sensor.personas()) || [];
        const lista = contexto === 'admin' ? todas : todas.filter((p) => p.tipo === 'operador');
        quien.innerHTML = lista.map((p) => `<option value="${p.tipo}:${p.id}">${esc(p.nombre)}</option>`).join('');
        if (previo) quien.value = previo;
      };
      llenar();
      quien.addEventListener('focus', llenar);
      sensor.refrescarPersonas = llenar;

      const f2 = (n) => String(n).padStart(2, '0');
      const aLocal = (ts) => {
        const d = new Date(ts);
        return `${d.getFullYear()}-${f2(d.getMonth() + 1)}-${f2(d.getDate())}T${f2(d.getHours())}:${f2(d.getMinutes())}`;
      };
      const campoFecha = dock.querySelector('[data-fecha]');
      const rotulo = dock.querySelector('[data-hora]');
      const pintarHora = () => {
        rotulo.textContent = `(ahora: ${TV.util.fmtFechaHora(TV.ahora())})`;
        if (document.activeElement !== campoFecha) campoFecha.value = aLocal(TV.ahora());
      };
      const ponerHora = async (iso) => {
        const r = await TV.api.post('/api/dev/reloj', { ahora: iso });
        TV.sincronizarHora(r.ts);
        pintarHora();
        window.dispatchEvent(new CustomEvent('tv:hora'));
      };
      pintarHora();
      setInterval(pintarHora, 5000);

      dock.querySelector('[data-poner]').addEventListener('click', () => {
        const [tipo, id] = (quien.value || ':').split(':');
        if (tipo) sensor.poner({ tipo, id: Number(id) });
      });
      dock.querySelector('[data-fallo]').addEventListener('click', () => sensor.poner(null));
      dock.querySelector('[data-aplicar]').addEventListener('click', () => campoFecha.value && ponerHora(campoFecha.value));
      dock.querySelector('[data-real]').addEventListener('click', () => ponerHora(null));
      dock.querySelectorAll('[data-sumar]').forEach((b) => b.addEventListener('click', () => ponerHora(aLocal(TV.ahora() + Number(b.dataset.sumar) * 60000))));
      dock.querySelector('[data-purgar]')?.addEventListener('click', async () => {
        const r = await TV.api.post('/api/dev/purgar');
        TV.ui.toast(r.purgados.length ? `Borrado definitivo de ${r.purgados.length} operador(es)` : 'Ninguna baja ha cumplido los 30 días');
        window.dispatchEvent(new CustomEvent('tv:datos'));
      });
      document.body.append(dock);
      sensor.reubicar();
    },

    // El simulador vive dentro del diálogo abierto (si no, el <dialog> modal lo dejaría inactivo)
    reubicar() {
      if (!dock) return;
      const abiertos = document.querySelectorAll('dialog[open]');
      (abiertos[abiertos.length - 1] || document.body).append(dock);
    },
  };

  TV.sensor = sensor;
})(window.TV);
