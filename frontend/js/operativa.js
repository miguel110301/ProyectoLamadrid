'use strict';
/*
 * Interfaz operativa. La pantalla siempre espera una huella; el servidor identifica a la persona y decide solo
 * si es su entrada o su salida. Aquí solo se muestran los resultados que llegan por eventos.
 * El navegador no guarda datos ni dice quién es nadie: lo único que envía es el formulario de incidencias
 * y la confirmación de una salida anticipada.
 */
(function (TV) {
  const { esc, fmtHoraSeg, fmtHora, fmtFechaLarga, durLarga, durCorta, pad, ymd } = TV.util;
  const { ui, sensor, api } = TV;
  const $ = (id) => document.getElementById(id);

  $('btn-incidencia').innerHTML = `${ui.icono('alerta')}<span>Registrar incidencia</span>`;

  /* ---------- Reloj y panel "en turno" ---------- */
  function tick() {
    const d = new Date(TV.ahora());
    $('reloj').textContent = fmtHoraSeg(d);
    $('fecha').textContent = fmtFechaLarga(d);
  }
  tick();
  setInterval(tick, 500);

  async function pintarEnTurno() {
    try {
      const filas = await api.get('/api/kiosko/en-turno');
      $('en-turno').innerHTML = filas.length
        ? filas.map((f) => `<li><span>${esc(f.nombre)}<small>Hasta las ${esc(f.fin)}</small></span><span class="insignia insignia--ok">${fmtHora(f.entrada_ts)}</span></li>`).join('')
        : '<li class="vacio">Nadie ha registrado entrada todavía.</li>';
    } catch (e) {
      /* sin conexión: se conserva lo que ya estaba */
    }
  }
  // La hora oficial es la del servidor: se revisa cada 30 s (corrige también saltos al resincronizar el reloj de la PC)
  const sincronizarHora = () => api.get('/api/kiosko/hora').then((h) => TV.sincronizarHora(h.ts)).catch(() => {});
  setInterval(() => {
    sincronizarHora();
    pintarEnTurno();
  }, 30000);
  window.addEventListener('tv:hora', pintarEnTurno);

  /* ---------- Estado del sensor y de la conexión con el sistema ---------- */
  $('sensor-ico').innerHTML = ui.icono('huella');
  const normal = () => {
    $('sensor-card').dataset.estado = '';
    $('sensor-titulo').textContent = 'Coloca tu dedo en el sensor';
    $('sensor-texto').textContent = 'El sistema detecta solo si es tu entrada o tu salida.';
  };
  normal();
  sensor.alCambiarConexion((estado) => {
    if (estado === 'desconectado') {
      $('sensor-card').dataset.estado = 'error';
      $('sensor-titulo').textContent = 'Sin conexión con el sistema';
      $('sensor-texto').textContent = 'Reconectando… si tarda, avisa al administrador.';
    } else {
      normal();
      if (estado === 'conectado') {
        sincronizarHora();
        pintarEnTurno();
      }
    }
  });

  /* ---------- Avisos por cada evento del servidor ---------- */
  const mensajeLlegada = {
    'a-tiempo': () => `<span class="insignia insignia--ok estado-entrada">Llegaste a tiempo</span>`,
    retardo: (ev) => `<span class="insignia insignia--warn estado-entrada">Retardo · ${durCorta(ev.min_tarde)} después de la hora de entrada</span>`,
    falta: (ev) => `<span class="insignia insignia--err estado-entrada">Se registra falta · ${durCorta(ev.min_tarde)} después de la hora de entrada</span>`,
  };

  function mostrarSalida(ev) {
    return ui.aviso({
      tono: 'exito',
      titulo: `Registro de salida con éxito a las ${fmtHoraSeg(ev.ts)}`,
      mensaje: `Estuviste en turno <strong>${durCorta(ev.trabajado_min)}</strong>.`,
      detalle: `${esc(ev.operador)}${ev.falto_min > 0 ? ` · Te faltaron ${durCorta(ev.falto_min)} para cumplir tu turno` : ''}`,
      autocierre: 12000,
    });
  }

  async function alEvento(ev) {
    switch (ev.evento) {
      case 'no-reconocida':
        return ui.aviso({ tono: 'error', titulo: 'Huella no reconocida', mensaje: 'No se pudo identificar la huella.', detalle: 'Limpia el dedo, colócalo bien sobre el sensor e intenta de nuevo.', autocierre: 5000 });
      case 'administrador':
        return ui.aviso({ tono: 'info', titulo: 'Huella de administrador', mensaje: 'Las huellas de administración no registran asistencia.', detalle: 'Para entrar a la administración usa «Administración» en la parte superior.', autocierre: 6000 });
      case 'duplicado':
        return ui.aviso({ tono: 'info', titulo: 'Tu registro ya quedó guardado', mensaje: `${esc(ev.operador)}, tu lectura anterior ya se registró.`, autocierre: 4000 });
      case 'sin-turno':
        return ui.aviso({ tono: 'aviso', titulo: 'No tienes un turno programado ahora', mensaje: `${esc(ev.operador)}, no hay un turno tuyo que pueda registrarse en este momento.`, detalle: `Puedes registrar entrada desde ${ev.anticipo_min} minutos antes de tu turno. Si crees que es un error, consulta al administrador.`, autocierre: 10000 });
      case 'entrada':
        pintarEnTurno();
        return ui.aviso({
          tono: ev.llegada === 'a-tiempo' ? 'exito' : 'aviso',
          titulo: `Registro de entrada con éxito a las ${fmtHoraSeg(ev.ts)}`,
          mensaje: mensajeLlegada[ev.llegada](ev),
          detalle: `${esc(ev.operador)} · Turno ${esc(ev.turno)}${ev.llegada === 'falta' ? ' · Debes cubrir tu turno; la falta puede justificarla el administrador' : ''}`,
          autocierre: 12000,
        });
      case 'confirmar-salida': {
        const ok = await ui.confirmar({
          titulo: 'Aún no termina tu turno',
          mensaje: `Te faltan <strong>${durLarga(ev.faltan_min)}</strong> para salir.<br />¿Estás seguro de registrar tu salida antes de terminar el horario de turno?`,
          aceptar: 'Registrar salida',
          cancelar: 'Cancelar',
        });
        try {
          const r = await api.post('/api/kiosko/confirmar-salida', { aceptar: ok });
          pintarEnTurno();
          if (r.evento === 'salida') return mostrarSalida(r);
        } catch (e) {
          return ui.aviso({ tono: 'error', titulo: 'No se pudo registrar la salida', mensaje: esc(e.message), detalle: 'Vuelve a colocar tu huella.', autocierre: 8000 });
        }
        return;
      }
      case 'salida':
        pintarEnTurno();
        return mostrarSalida(ev);
      case 'incidencia-incompleta':
      case 'incidencia-registrada':
        return; // solo importan con el formulario abierto
      case 'error':
        return ui.aviso({ tono: 'error', titulo: 'No se pudo completar el registro', mensaje: esc(ev.mensaje || ''), autocierre: 8000 });
    }
  }

  /* ---------- Incidencias: se llena el formulario y la huella termina el registro ---------- */
  function formularioIncidencia() {
    const ahora = new Date(TV.ahora());
    const nodo = document.createElement('form');
    nodo.noValidate = true;
    nodo.innerHTML = `
      <div class="modal__cab"><h2>Registrar incidencia</h2></div>
      <div class="modal__cuerpo">
        <p class="regla">Se guardará automáticamente: <strong>${TV.util.fmtFecha(ymd(ahora))}</strong> a las <strong>${fmtHoraSeg(ahora)}</strong>.</p>
        <div class="rejilla">
          <label class="campo" data-campo="hora">
            <span class="campo__etiqueta">Hora de la incidencia <span class="req">*</span></span>
            <input type="time" name="hora" value="${pad(ahora.getHours())}:${pad(ahora.getMinutes())}" required />
            <span class="campo__error" hidden></span>
          </label>
          <label class="campo" data-campo="programa">
            <span class="campo__etiqueta">Programa (opcional)</span>
            <input type="text" name="programa" maxlength="80" placeholder="Ej. Noticiero" />
          </label>
        </div>
        <label class="campo" data-campo="tipo">
          <span class="campo__etiqueta">Tipo de incidencia <span class="req">*</span></span>
          <select name="tipo" required>
            <option value="">Selecciona un tipo…</option>
            ${TV.TIPOS.map((t) => `<option value="${t.id}">${esc(t.nombre)}</option>`).join('')}
          </select>
          <span class="campo__error" hidden></span>
        </label>
        <div class="campo" data-campo="duracion" hidden>
          <span class="campo__etiqueta">Duración de la incidencia <span class="req">*</span></span>
          <div class="rejilla" style="grid-template-columns: 1fr 1fr">
            <label class="campo"><input type="number" name="dh" min="0" max="23" value="0" inputmode="numeric" aria-label="Horas" /><span class="campo__ayuda">horas</span></label>
            <label class="campo"><input type="number" name="dm" min="0" max="59" value="0" inputmode="numeric" aria-label="Minutos" /><span class="campo__ayuda">minutos</span></label>
          </div>
          <span class="campo__error" hidden></span>
        </div>
        <label class="campo" data-campo="observacion">
          <span class="campo__etiqueta">Observación <span class="req">*</span></span>
          <textarea name="observacion" maxlength="1000" placeholder="Describe a detalle la falla o incidencia que estás registrando"></textarea>
          <span class="campo__error" hidden></span>
        </label>
        <div class="sensor-pie" role="status" aria-live="polite">
          <span class="sensor-pie__ico">${ui.icono('huella')}</span>
          <span data-estado>Al terminar, coloca tu huella en el sensor para registrar la incidencia.</span>
        </div>
      </div>
      <div class="modal__pie modal__pie--sim">
        <div data-sim></div>
        <button type="button" class="btn btn--secundario" data-cancelar>Cancelar</button>
      </div>`;
    return nodo;
  }

  async function registrarIncidencia() {
    await sincronizarHora();
    const form = formularioIncidencia();
    const m = ui.modal(form, { ancho: '44rem', cerrable: false });
    // Con el formulario abierto el servidor ya no toma las huellas como entrada/salida; manda latidos mientras siga abierto
    api.post('/api/kiosko/incidencia/abrir').catch(() => {});
    const latido = setInterval(() => api.post('/api/kiosko/incidencia/abrir').catch(() => {}), 60000);
    sensor.visible(false);
    sensor.simuladorEnLinea().then((s) => form.querySelector('[data-sim]').append(s));

    const campo = (n) => form.querySelector(`[data-campo="${n}"]`);
    const estado = form.querySelector('[data-estado]');
    const pie = form.querySelector('.sensor-pie');
    const duracionRequerida = () => (TV.TIPOS.find((t) => t.id === form.tipo.value) || {}).duracion === true;
    const duracion = () => Number(form.dh.value || 0) * 60 + Number(form.dm.value || 0);

    const error = (nombre, texto) => {
      const c = campo(nombre);
      const e = c.querySelector('.campo__error');
      c.classList.toggle('campo--invalido', !!texto);
      e.hidden = !texto;
      e.textContent = texto || '';
      return !!texto;
    };
    const aviso = (texto, tono) => {
      estado.textContent = texto;
      pie.dataset.tono = tono || '';
    };

    // Devuelve los errores sin pintarlos (para decidir si el formulario ya está listo)
    function problemas() {
      const ahora = new Date(TV.ahora());
      return {
        hora: !form.hora.value ? 'Indica la hora de la incidencia.' : TV.util.aTs(ymd(ahora), form.hora.value) > ahora.getTime() ? 'La hora no puede ser posterior a la actual.' : '',
        tipo: form.tipo.value ? '' : 'Selecciona el tipo de incidencia.',
        duracion: duracionRequerida() && duracion() <= 0 ? 'Este tipo de incidencia requiere indicar la duración.' : '',
        observacion: form.observacion.value.trim() ? '' : 'La observación es obligatoria.',
      };
    }
    const completo = () => Object.values(problemas()).every((t) => !t);

    // El formulario completo se deja listo en el servidor; la huella lo envía. Si queda incompleto, se retira.
    let temporizador;
    function sincronizar() {
      clearTimeout(temporizador);
      temporizador = setTimeout(async () => {
        try {
          if (completo()) {
            await api.put('/api/kiosko/incidencia', {
              tipo: form.tipo.value,
              hora: form.hora.value,
              programa: form.programa.value.trim(),
              duracion_min: duracionRequerida() ? duracion() : null,
              observacion: form.observacion.value.trim(),
            });
            aviso('Listo. Coloca tu huella en el sensor para registrar la incidencia.', 'ok');
          } else {
            await api.del('/api/kiosko/incidencia/borrador');
            aviso('Completa los campos marcados y después coloca tu huella.', '');
          }
        } catch (e) {
          aviso(e.message, 'error');
        }
      }, 300);
    }
    // Los errores que ya se mostraron se actualizan al corregir el campo
    const refrescarErrores = () => Object.entries(problemas()).forEach(([k, t]) => campo(k).classList.contains('campo--invalido') && error(k, t));
    form.addEventListener('input', () => {
      refrescarErrores();
      sincronizar();
    });
    form.addEventListener('change', () => {
      campo('duracion').hidden = !duracionRequerida();
      refrescarErrores();
      sincronizar();
    });
    form.addEventListener('submit', (e) => e.preventDefault());

    const cerrarTodo = (valor) => {
      clearInterval(latido);
      clearTimeout(temporizador);
      api.del('/api/kiosko/incidencia').catch(() => {});
      sensor.visible(true);
      m.cerrar(valor);
    };
    form.querySelector('[data-cancelar]').addEventListener('click', () => cerrarTodo(null));

    const quitar = sensor.empujar((ev) => {
      if (ev.evento === 'incidencia-registrada') {
        clearInterval(latido);
        clearTimeout(temporizador);
        sensor.visible(true);
        m.cerrar(true);
        ui.aviso({
          tono: 'exito',
          titulo: 'Incidencia registrada',
          mensaje: esc((TV.TIPOS.find((t) => t.id === form.tipo.value) || {}).nombre || ''),
          detalle: `${esc(ev.operador)} · ${TV.util.fmtFechaHora(ev.ts)}`,
          autocierre: 8000,
        });
      } else if (ev.evento === 'incidencia-incompleta') {
        const p = problemas();
        Object.entries(p).forEach(([k, t]) => error(k, t));
        form.querySelector('.campo--invalido input, .campo--invalido select, .campo--invalido textarea')?.focus();
        aviso('Completa los campos marcados y vuelve a colocar tu huella.', 'error');
      } else if (ev.evento === 'no-reconocida') aviso('Huella no reconocida. Intenta de nuevo.', 'error');
      else if (ev.evento === 'error') aviso(ev.mensaje || 'No se pudo registrar la incidencia.', 'error');
    });
    m.promesa.then(quitar);
  }
  $('btn-incidencia').addEventListener('click', registrarIncidencia);

  /* ---------- Arranque ---------- */
  async function iniciar() {
    try {
      const [tipos, hora] = await Promise.all([api.get('/api/kiosko/tipos-incidencia'), api.get('/api/kiosko/hora')]);
      TV.TIPOS.splice(0, TV.TIPOS.length, ...tipos.map((t) => ({ id: t.id, nombre: t.nombre, duracion: !!t.requiere_duracion })));
      TV.sincronizarHora(hora.ts);
    } catch (e) {
      /* el aviso de conexión ya lo muestra el estado del sensor */
    }
    pintarEnTurno();
  }
  sensor.empujar(alEvento);
  sensor.conectar();
  sensor.montarSimulador('operador');
  iniciar();
})(window.TV);
