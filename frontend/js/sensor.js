'use strict';
/*
 * Lector biométrico: la pantalla siempre está esperando una huella.
 *
 * El sensor real avisa al backend cuando detecta un dedo; aquí el simulador de la esquina
 * hace ese papel. Cada pantalla (o diálogo) que necesite la huella "empuja" un manejador en
 * una pila: solo el de arriba recibe la lectura. Al cerrarse, deja de recibirla y vuelve a
 * recibirla el de abajo. En producción solo cambia la fuente de los eventos (WebSocket/SSE
 * desde FastAPI) en lugar del simulador; los manejadores no cambian.
 *
 * Evento: { operadorId: string | null }  (null = huella no reconocida)
 */
(function (TV) {
  const { esc } = TV.util;
  const pila = [];
  let dock = null;

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

    // El simulador vive dentro del diálogo abierto (si no, el <dialog> modal lo dejaría inactivo)
    reubicar() {
      if (!dock) return;
      const abiertos = document.querySelectorAll('dialog[open]');
      (abiertos[abiertos.length - 1] || document.body).append(dock);
    },

    // Simulador incrustado en un formulario (p. ej. incidencias): misma lectura, a la vista dentro del diálogo
    simuladorEnLinea() {
      const caja = document.createElement('div');
      caja.className = 'sim-linea';
      const ops = TV.db.get().operadores.filter((o) => o.huella);
      caja.innerHTML = `
        <span class="sim-linea__rotulo">Simulador de sensor · solo prototipo</span>
        <label class="campo"><span class="solo-lectores">Huella de</span>
          <select data-quien>${ops.map((o) => `<option value="${o.id}">${esc(o.nombre)}</option>`).join('')}</select></label>
        <button type="button" class="btn btn--primario btn--chico" data-poner>${TV.ui.icono('huella')} Simular huella</button>
        <button type="button" class="btn btn--secundario btn--chico" data-fallo>No reconocida</button>`;
      const quien = caja.querySelector('[data-quien]');
      caja.querySelector('[data-poner]').addEventListener('click', () => quien.value && sensor.emitir({ operadorId: quien.value }));
      caja.querySelector('[data-fallo]').addEventListener('click', () => sensor.emitir({ operadorId: null }));
      return caja;
    },

    // Dentro del panel administrativo el sensor no se usa: el simulador se oculta
    visible(v) {
      if (dock) dock.hidden = !v;
    },

    // contexto 'admin' agrega al administrador entre las huellas que se pueden simular
    montarSimulador(contexto = 'operador') {
      dock = document.createElement('details');
      dock.className = 'sim';
      dock.open = true;
      dock.innerHTML = `
        <summary>Simulador de sensor · solo prototipo</summary>
        <div class="sim__cuerpo">
          <label class="campo"><span class="campo__etiqueta">Huella de</span><select data-quien></select></label>
          <div class="acciones">
            <button type="button" class="btn btn--primario btn--chico" data-poner>Poner dedo</button>
            <button type="button" class="btn btn--secundario btn--chico" data-fallo>No reconocida</button>
          </div>
        </div>`;
      const quien = dock.querySelector('[data-quien]');
      const llenar = () => {
        const previo = quien.value;
        const ops = TV.db.get().operadores.filter((o) => o.huella);
        quien.innerHTML =
          (contexto === 'admin' ? '<option value="admin">Administrador</option>' : '') +
          ops.map((o) => `<option value="${o.id}">${esc(o.nombre)}</option>`).join('');
        if (previo) quien.value = previo;
      };
      llenar();
      quien.addEventListener('focus', llenar);
      dock.querySelector('[data-poner]').addEventListener('click', () => quien.value && sensor.emitir({ operadorId: quien.value }));
      dock.querySelector('[data-fallo]').addEventListener('click', () => sensor.emitir({ operadorId: null }));
      document.body.append(dock);
      sensor.reubicar();
    },
  };

  TV.sensor = sensor;
})(window.TV);
