'use strict';
/* Componentes de interfaz compartidos: iconos, modales, avisos, lector biométrico (simulado) e impresión. */
(function (TV) {
  const { esc } = TV.util;

  const ICONOS = {
    huella:
      '<path d="M12 10a2 2 0 0 0-2 2c0 1.02-.1 2.51-.26 4"/><path d="M14 13.12c0 2.38 0 6.38-1 8.88"/><path d="M17.29 21.02c.12-.6.43-2.3.5-3.02"/><path d="M2 12a10 10 0 0 1 18-6"/><path d="M2 16h.01"/><path d="M21.8 16c.2-2 .131-5.354 0-6"/><path d="M5 19.5C5.5 18 6 15 6 12a6 6 0 0 1 .34-2"/><path d="M8.65 22c.21-.66.45-1.32.57-2"/><path d="M9 6.8a6 6 0 0 1 9 5.2v2"/>',
    entrada: '<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" x2="3" y1="12" y2="12"/>',
    salida: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" x2="9" y1="12" y2="12"/>',
    alerta: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    usuarios: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    usuario: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
    lista: '<rect width="8" height="4" x="8" y="2" rx="1" ry="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    imprimir: '<path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 9V3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v6"/><rect x="6" y="14" width="12" height="8" rx="1"/>',
    mas: '<path d="M5 12h14"/><path d="M12 5v14"/>',
    editar: '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/>',
    reloj: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>',
    ok: '<path d="M20 6 9 17l-5-5"/>',
    x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    candado: '<rect width="18" height="11" x="3" y="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
  };
  const icono = (n, cls = '') =>
    `<svg class="ico ${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONOS[n] || ''}</svg>`;

  /* ---------- Modales (<dialog> nativo) ---------- */
  function modal(contenido, { ancho = '32rem', cerrable = true, clase = '' } = {}) {
    const dlg = document.createElement('dialog');
    dlg.className = 'modal ' + clase;
    dlg.style.setProperty('--ancho', ancho);
    if (typeof contenido === 'string') dlg.innerHTML = contenido;
    else dlg.append(contenido);
    document.body.append(dlg);
    let resolver;
    const promesa = new Promise((r) => (resolver = r));
    const cerrar = (valor) => {
      if (dlg.open) dlg.close();
      dlg.remove();
      if (TV.sensor) TV.sensor.reubicar();
      resolver(valor);
    };
    dlg.addEventListener('cancel', (e) => {
      e.preventDefault();
      if (cerrable) cerrar(undefined);
    });
    dlg.showModal();
    if (TV.sensor) TV.sensor.reubicar();
    return { el: dlg, cerrar, promesa };
  }

  const TONOS = { exito: 'ok', aviso: 'alerta', error: 'x', info: 'reloj' };

  // Mensaje de resultado grande (visible a distancia en el Control Maestro)
  function aviso({ tono = 'info', titulo, mensaje = '', detalle = '', autocierre = 0 }) {
    const nodo = document.createElement('div');
    nodo.className = `aviso aviso--${tono}`;
    nodo.innerHTML = `
      <div class="aviso__icono">${icono(TONOS[tono] || 'reloj')}</div>
      <h2 class="aviso__titulo">${esc(titulo)}</h2>
      ${mensaje ? `<p class="aviso__mensaje">${mensaje}</p>` : ''}
      ${detalle ? `<p class="aviso__detalle">${detalle}</p>` : ''}
      <button class="btn btn--primario btn--grande" data-cerrar autofocus>Aceptar</button>`;
    const m = modal(nodo, { ancho: '34rem' });
    nodo.querySelector('[data-cerrar]').addEventListener('click', () => m.cerrar(true));
    if (autocierre) setTimeout(() => m.cerrar(true), autocierre);
    // Si llega otra huella mientras se muestra el mensaje, se cierra y esa lectura se atiende enseguida
    const quitar = TV.sensor.empujar((ev) => {
      quitar();
      m.cerrar(true);
      TV.sensor.emitir(ev);
    });
    m.promesa.then(quitar);
    return m.promesa;
  }

  function confirmar({ titulo, mensaje, aceptar = 'Aceptar', cancelar = 'Cancelar', tono = 'aviso' }) {
    const nodo = document.createElement('div');
    nodo.className = `aviso aviso--${tono}`;
    nodo.innerHTML = `
      <div class="aviso__icono">${icono(TONOS[tono] || 'alerta')}</div>
      <h2 class="aviso__titulo">${esc(titulo)}</h2>
      <p class="aviso__mensaje">${mensaje}</p>
      <div class="acciones acciones--centro">
        <button class="btn btn--secundario btn--grande" data-valor="0" autofocus>${esc(cancelar)}</button>
        <button class="btn btn--primario btn--grande" data-valor="1">${esc(aceptar)}</button>
      </div>`;
    const m = modal(nodo, { ancho: '36rem', cerrable: false });
    nodo.querySelectorAll('[data-valor]').forEach((b) => b.addEventListener('click', () => m.cerrar(b.dataset.valor === '1')));
    m.promesa.then(TV.sensor.empujar(() => {}));
    return m.promesa;
  }

  function toast(texto, tono = 'exito') {
    let cont = document.getElementById('toasts');
    if (!cont) {
      cont = document.createElement('div');
      cont.id = 'toasts';
      cont.setAttribute('role', 'status');
      document.body.append(cont);
    }
    const t = document.createElement('div');
    t.className = `toast toast--${tono}`;
    t.textContent = texto;
    cont.append(t);
    setTimeout(() => t.remove(), 3800);
  }

  /* ---------- Impresión / PDF con hoja membretada ---------- */
  function imprimir({ titulo, meta = '', html, apaisado = false }) {
    let hoja = document.getElementById('hoja');
    if (!hoja) {
      hoja = document.createElement('div');
      hoja.id = 'hoja';
      hoja.setAttribute('aria-hidden', 'true');
      document.body.append(hoja);
    }
    // Membrete provisional con el logo de tv.uaq.mx: se reemplaza por el formato oficial cuando el cliente lo entregue.
    hoja.className = apaisado ? 'hoja--apaisada' : '';
    hoja.innerHTML = `
      <header class="hoja__membrete">
        <img class="hoja__logo" src="assets/img/logo_tvuaq.png" alt="TvUAQ" />
        <div class="hoja__institucion">
          <strong>Control Maestro</strong>
          <span>Sistema de registro de incidencias</span>
        </div>
      </header>
      <h1 class="hoja__titulo">${esc(titulo)}</h1>
      <p class="hoja__meta">${meta}</p>
      <div class="hoja__cuerpo">${html}</div>
      <footer class="hoja__pie">Emitido el ${TV.util.fmtFechaHora(TV.ahora())}</footer>`;
    const limpiar = () => {
      hoja.innerHTML = '';
      window.removeEventListener('afterprint', limpiar);
    };
    window.addEventListener('afterprint', limpiar);
    window.print();
  }

  TV.ui = { icono, modal, aviso, confirmar, toast, imprimir };
})(window.TV);
