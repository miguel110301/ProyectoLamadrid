'use strict';
/*
 * Interfaz operativa. La pantalla siempre espera una huella y el sistema decide solo:
 * si la persona tiene una entrada abierta es su salida, y si no, es su entrada.
 */
(function (TV) {
  const { esc, fmtHoraSeg, fmtHora, fmtFechaLarga, durLarga, durCorta, pad, ymd } = TV.util;
  const { ui, sensor } = TV;
  const $ = (id) => document.getElementById(id);

  $('btn-incidencia').innerHTML = `${ui.icono('alerta')}<span>Registrar incidencia</span>`;

  /* ---------- Reloj y panel "en turno" ---------- */
  function tick() {
    const d = new Date();
    $('reloj').textContent = fmtHoraSeg(d);
    $('fecha').textContent = fmtFechaLarga(d);
  }
  tick();
  setInterval(tick, 500);

  function pintarEnTurno() {
    const ahora = Date.now();
    const filas = TV.db
      .get()
      .operadores.map((o) => ({ o, r: TV.calc.registroVigente(o.id, ahora) }))
      .filter((x) => x.r);
    $('en-turno').innerHTML = filas.length
      ? filas
          .map(
            ({ o, r }) =>
              `<li><span>${esc(o.nombre)}<small>Turno ${r.turno.inicio}–${r.turno.fin}</small></span><span class="insignia insignia--ok">${fmtHora(r.entradaTs)}</span></li>`
          )
          .join('')
      : '<li class="vacio">Nadie ha registrado entrada todavía.</li>';
  }
  pintarEnTurno();
  setInterval(pintarEnTurno, 30000);

  /* ---------- Estado del sensor ---------- */
  $('sensor-ico').innerHTML = ui.icono('huella');
  $('sensor-titulo').textContent = 'Coloca tu dedo en el sensor';
  $('sensor-texto').textContent = 'El sistema detecta solo si es tu entrada o tu salida.';

  /* ---------- Lectura de huella en la pantalla principal ---------- */
  async function alLeer({ operadorId }) {
    if (!operadorId) {
      return ui.aviso({
        tono: 'error',
        titulo: 'Huella no reconocida',
        mensaje: 'No se pudo identificar la huella.',
        detalle: 'Limpia el dedo, colócalo bien sobre el sensor e intenta de nuevo.',
        autocierre: 5000,
      });
    }

    const op = TV.db.operador(operadorId);
    const ahora = Date.now();

    // La misma persona no puede registrar dos veces con un solo toque del dedo
    const ultimo = TV.db.get().registros.filter((r) => r.operadorId === op.id).reduce((a, r) => Math.max(a, r.entradaTs, r.salidaTs || 0), 0);
    if (ahora - ultimo < TV.CFG.reboteSeg * 1000) {
      return ui.aviso({
        tono: 'info',
        titulo: 'Tu registro ya quedó guardado',
        mensaje: `${esc(op.nombre)}, tu lectura de las ${fmtHoraSeg(ultimo)} ya se registró.`,
        autocierre: 4000,
      });
    }

    const abierto = TV.calc.registroVigente(op.id, ahora);
    return abierto ? procesarSalida(op, abierto, ahora) : procesarEntrada(op, ahora);
  }

  async function procesarEntrada(op, ahora) {
    const t = TV.calc.turnoParaEntrada(op, ahora);
    if (!t) {
      return ui.aviso({
        tono: 'aviso',
        titulo: 'No tienes un turno programado ahora',
        mensaje: `${esc(op.nombre)}, no hay un turno tuyo que pueda registrarse en este momento.`,
        detalle: `Puedes registrar entrada desde ${TV.CFG.anticipoEntradaMin} minutos antes de tu turno. Si crees que es un error, consulta al administrador.`,
        autocierre: 10000,
      });
    }

    TV.db.get().registros.push({
      id: TV.db.uid(),
      operadorId: op.id,
      fecha: t.fecha,
      turno: t.turno,
      iniTs: t.iniTs,
      finTs: t.finTs,
      entradaTs: ahora,
      salidaTs: null,
      salidaAnticipada: false,
    });
    TV.db.guardar();
    pintarEnTurno();

    const llegada = TV.calc.estadoEntrada(ahora, t.iniTs);
    const minTarde = Math.round((ahora - t.iniTs) / TV.MIN);
    const mensajes = {
      'a-tiempo': `<span class="insignia insignia--ok estado-entrada">Llegaste a tiempo</span>`,
      retardo: `<span class="insignia insignia--warn estado-entrada">Retardo · ${durCorta(minTarde)} después de las ${t.turno.inicio}</span>`,
      falta: `<span class="insignia insignia--err estado-entrada">Se registra falta · ${durCorta(minTarde)} después de las ${t.turno.inicio}</span>`,
    };
    return ui.aviso({
      tono: llegada === 'a-tiempo' ? 'exito' : 'aviso',
      titulo: `Registro de entrada con éxito a las ${fmtHoraSeg(ahora)}`,
      mensaje: mensajes[llegada],
      detalle: `${esc(op.nombre)} · Turno ${t.turno.inicio}–${t.turno.fin}${llegada === 'falta' ? ' · Debes cubrir tu turno; la falta puede justificarla el administrador' : ''}`,
      autocierre: 12000,
    });
  }

  async function procesarSalida(op, reg, ahora) {
    const faltanMin = (reg.finTs - ahora) / TV.MIN;
    let anticipada = false;
    if (faltanMin > TV.CFG.toleranciaSalidaMin) {
      const ok = await ui.confirmar({
        titulo: 'Aún no termina tu turno',
        mensaje: `Te faltan <strong>${durLarga(Math.ceil(faltanMin))}</strong> para salir.<br />¿Estás seguro de registrar tu salida antes de terminar el horario de turno?`,
        aceptar: 'Registrar salida',
        cancelar: 'Cancelar',
      });
      if (!ok) return;
      anticipada = true;
    }

    const ts = Date.now(); // la hora real del registro es la de la confirmación
    reg.salidaTs = ts;
    reg.salidaAnticipada = anticipada;
    TV.db.guardar();
    pintarEnTurno();

    const trabajado = Math.round((ts - reg.entradaTs) / TV.MIN);
    const falto = Math.max(0, (reg.finTs - reg.iniTs) / TV.MIN - trabajado);
    return ui.aviso({
      tono: 'exito',
      titulo: `Registro de salida con éxito a las ${fmtHoraSeg(ts)}`,
      mensaje: `Estuviste en turno <strong>${durCorta(trabajado)}</strong>.`,
      detalle: `${esc(op.nombre)}${falto > 0 ? ` · Te faltaron ${durCorta(falto)} para cumplir tu turno` : ''}`,
      autocierre: 12000,
    });
  }

  /* ---------- Incidencias: se llena el formulario y la huella termina el registro ---------- */
  function formularioIncidencia() {
    const ahora = new Date();
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

  function registrarIncidencia() {
    const form = formularioIncidencia();
    const m = ui.modal(form, { ancho: '44rem', cerrable: false });
    // En este formulario el simulador va dentro del diálogo; el flotante se oculta mientras esté abierto
    form.querySelector('[data-sim]').append(sensor.simuladorEnLinea());
    sensor.visible(false);
    m.promesa.then(() => sensor.visible(true));
    const campo = (n) => form.querySelector(`[data-campo="${n}"]`);
    const estado = form.querySelector('[data-estado]');
    const pie = form.querySelector('.sensor-pie');
    const duracionRequerida = () => (TV.TIPOS.find((t) => t.id === form.tipo.value) || {}).duracion === true;

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

    form.tipo.addEventListener('change', () => {
      campo('duracion').hidden = !duracionRequerida();
      error('tipo', '');
      error('duracion', '');
    });
    form.addEventListener('submit', (e) => e.preventDefault());
    form.querySelector('[data-cancelar]').addEventListener('click', () => m.cerrar(null));

    function validar() {
      const ahora = new Date();
      const durMin = Number(form.dh.value || 0) * 60 + Number(form.dm.value || 0);
      let mal = false;
      mal = error('hora', !form.hora.value ? 'Indica la hora de la incidencia.' : TV.util.aTs(ymd(ahora), form.hora.value) > ahora.getTime() ? 'La hora no puede ser posterior a la actual.' : '') || mal;
      mal = error('tipo', form.tipo.value ? '' : 'Selecciona el tipo de incidencia.') || mal;
      mal = error('duracion', duracionRequerida() && durMin <= 0 ? 'Este tipo de incidencia requiere indicar la duración.' : '') || mal;
      mal = error('observacion', form.observacion.value.trim() ? '' : 'La observación es obligatoria.') || mal;
      if (mal) form.querySelector('.campo--invalido input, .campo--invalido select, .campo--invalido textarea')?.focus();
      return !mal;
    }

    // Mientras el formulario esté abierto, la huella es la que "envía" el registro
    const quitar = sensor.empujar(({ operadorId }) => {
      if (!validar()) return aviso('Completa los campos marcados y vuelve a colocar tu huella.', 'error');
      if (!operadorId) return aviso('Huella no reconocida. Intenta de nuevo.', 'error');

      const reg = new Date();
      TV.db.get().incidencias.push({
        id: TV.db.uid(),
        operadorId,
        fecha: ymd(reg),
        hora: form.hora.value,
        registradoTs: reg.getTime(),
        programa: form.programa.value.trim(),
        duracionMin: duracionRequerida() ? Number(form.dh.value || 0) * 60 + Number(form.dm.value || 0) : null,
        tipo: form.tipo.value,
        observacion: form.observacion.value.trim(),
      });
      TV.db.guardar();
      const tipo = TV.util.tipoNombre(form.tipo.value);
      m.cerrar(true);
      ui.aviso({
        tono: 'exito',
        titulo: 'Incidencia registrada',
        mensaje: esc(tipo),
        detalle: `${esc(TV.db.operador(operadorId).nombre)} · ${TV.util.fmtFechaHora(reg.getTime())}`,
        autocierre: 8000,
      });
    });
    m.promesa.then(quitar);
  }
  $('btn-incidencia').addEventListener('click', registrarIncidencia);

  // La pantalla principal queda escuchando desde que carga
  sensor.empujar(alLeer);
  sensor.montarSimulador('operador');
})(window.TV);
