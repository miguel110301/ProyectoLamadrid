'use strict';
/* Interfaz administrativa: acceso, alta de operadores, horarios y reportes. */
(function (TV) {
  const { esc, fmtFecha, fmtHora, durCorta, edad, ymd, aMin, parseYmd, tipoNombre } = TV.util;
  const { ui, sensor, DIAS, ORDEN_DIAS } = TV;
  const app = document.getElementById('app');

  // PROTOTIPO: credenciales de apoyo cuando falla el sensor. La validación real debe vivir en el backend.
  const USUARIO = 'admin';
  const CLAVE = 'admin';
  const SESION = 'tvuaq.admin';
  const autenticado = () => {
    try {
      return sessionStorage.getItem(SESION) === '1';
    } catch (e) {
      return false;
    }
  };
  const marcarSesion = (v) => {
    try {
      v ? sessionStorage.setItem(SESION, '1') : sessionStorage.removeItem(SESION);
    } catch (e) {
      /* sin sessionStorage: la sesión dura lo que dure la página */
    }
  };

  const hoy = () => ymd(new Date());
  const primeroDeMes = () => {
    const d = new Date();
    return ymd(new Date(d.getFullYear(), d.getMonth(), 1));
  };
  // Filtros que se conservan al cambiar de reporte
  const F = { pase: hoy(), preset: 'mes', desde: primeroDeMes(), hasta: hoy(), modoFecha: 'rango', fecha: hoy(), op: '', tipo: '', operador: '' };

  /* =========================================================
     ACCESO
     ========================================================= */
  function vistaAcceso() {
    document.title = 'Acceso · Control Maestro TvUAQ';
    app.innerHTML = `
      <div class="sitio">
        <header class="cab-sitio">
          <div class="barra"><div class="marca"><img class="marca__logo" src="assets/img/logo_tvuaq.png" alt="TvUAQ" /><span class="marca__texto">Control Maestro<small>Administración</small></span></div></div>
          <div class="cab-sitio__acciones"><a class="btn btn--secundario btn--chico" href="index.html">Ir al registro</a></div>
        </header>
        <main class="acceso">
          <div class="titulo-seccion"><h1>Acceso administrativo</h1><p>Coloca tu huella en el sensor o ingresa con usuario y contraseña.</p></div>
          <div class="sensor-card" id="a-sensor" role="status" aria-live="polite">
            <div class="sensor-card__ico">${ui.icono('huella')}</div>
            <div>
              <h2 class="sensor-card__titulo" id="a-sensor-titulo">Esperando huella</h2>
              <p class="sensor-card__texto" id="a-sensor-texto">Coloca tu dedo en el sensor para ingresar.</p>
            </div>
          </div>
          <div class="separador">o</div>
          <details id="a-clave">
            <summary>Ingresar con usuario y contraseña</summary>
            <form id="a-form" novalidate>
              <label class="campo">
                <span class="campo__etiqueta">Usuario</span>
                <input type="text" name="usuario" autocomplete="username" required />
              </label>
              <label class="campo">
                <span class="campo__etiqueta">Contraseña</span>
                <input type="password" name="clave" autocomplete="current-password" required />
              </label>
              <p class="campo__error" id="a-error" role="alert" hidden></p>
              <div><button class="btn btn--primario" type="submit">Entrar</button></div>
            </form>
          </details>
          <p class="nota-proto">Prototipo · usuario <strong>admin</strong> · contraseña <strong>admin</strong></p>
        </main>
        <footer class="pie-sitio"><span>Control Maestro TvUAQ · Sistema de registro de incidencias</span></footer>
      </div>`;

    const detalles = document.getElementById('a-clave');
    const titulo = document.getElementById('a-sensor-titulo');
    const texto = document.getElementById('a-sensor-texto');
    const tarjeta = document.getElementById('a-sensor');

    // Si el sensor falla, la alternativa de usuario y contraseña se abre sola
    const falla = (t, d) => {
      tarjeta.dataset.estado = 'error';
      titulo.textContent = t;
      texto.textContent = d;
      detalles.open = true;
    };

    const quitar = sensor.empujar(({ operadorId }) => {
      if (operadorId === 'admin') {
        quitar();
        return entrar();
      }
      if (!operadorId) return falla('Huella no reconocida', 'Intenta de nuevo o ingresa con usuario y contraseña.');
      falla('Sin permisos de administrador', 'Esa huella pertenece a un operador. Usa la huella del administrador o tu usuario y contraseña.');
    });

    document.getElementById('a-form').addEventListener('submit', (e) => {
      e.preventDefault();
      const f = e.target;
      const err = document.getElementById('a-error');
      if (f.usuario.value.trim() === USUARIO && f.clave.value === CLAVE) {
        quitar();
        return entrar();
      }
      err.hidden = false;
      err.textContent = 'Usuario o contraseña incorrectos.';
      f.clave.value = '';
      f.clave.focus();
    });
  }

  function entrar() {
    marcarSesion(true);
    sensor.visible(false);
    if (!location.hash) location.hash = '#/operadores';
    armarShell();
  }
  function salir() {
    marcarSesion(false);
    sensor.visible(true);
    location.hash = '';
    vistaAcceso();
  }

  /* =========================================================
     ESTRUCTURA Y RUTAS
     ========================================================= */
  const RUTAS = {
    operadores: { titulo: 'Operadores', icono: 'usuarios', vista: vistaOperadores },
    pase: { titulo: 'Registro de asistencia', icono: 'lista', vista: vistaPase },
    asistencia: { titulo: 'Tabla de asistencias', icono: 'lista', vista: vistaAsistencia },
    individual: { titulo: 'Reporte individual', icono: 'usuario', vista: vistaIndividual },
    incidencias: { titulo: 'Incidencias', icono: 'alerta', vista: vistaIncidencias },
  };

  function armarShell() {
    const links = Object.entries(RUTAS)
      .map(([id, r]) => `<li><a href="#/${id}" data-ruta="${id}">${r.titulo}</a></li>`)
      .join('');
    app.innerHTML = `
      <div class="sitio">
        <header class="cab-sitio">
          <nav class="barra" aria-label="Secciones">
            <div class="marca"><img class="marca__logo" src="assets/img/logo_tvuaq.png" alt="TvUAQ" /><span class="marca__texto">Control Maestro<small>Administración</small></span></div>
            <ul class="barra__links">${links}</ul>
          </nav>
          <div class="cab-sitio__acciones">
            <a class="btn btn--secundario btn--chico" href="index.html">Ir al registro</a>
            <button class="btn btn--primario btn--chico" id="b-salir" type="button">Cerrar sesión</button>
          </div>
        </header>
        <main class="contenido" id="vista"></main>
        <footer class="pie-sitio">
          <span>Control Maestro TvUAQ · Sistema de registro de incidencias</span>
          <button id="b-demo" type="button">Restablecer datos de demostración</button>
        </footer>
      </div>`;
    document.getElementById('b-salir').addEventListener('click', salir);
    document.getElementById('b-demo').addEventListener('click', async () => {
      const ok = await ui.confirmar({
        titulo: 'Restablecer datos de demostración',
        mensaje: 'Se borrarán los operadores, asistencias e incidencias actuales y se cargarán datos de ejemplo.',
        aceptar: 'Restablecer',
      });
      if (!ok) return;
      TV.db.reiniciar();
      ruta();
      ui.toast('Datos de demostración cargados');
    });
    ruta();
  }

  function ruta() {
    const [id, query = ''] = (location.hash.replace(/^#\/?/, '') || 'operadores').split('?');
    const r = RUTAS[id] || RUTAS.operadores;
    const idReal = RUTAS[id] ? id : 'operadores';
    new URLSearchParams(query).forEach((v, k) => {
      if (k in F) F[k] = v;
    });
    document.title = `${r.titulo} · Administración TvUAQ`;
    document.querySelectorAll('[data-ruta]').forEach((a) => (a.dataset.ruta === idReal ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
    r.vista(document.getElementById('vista'));
    window.scrollTo(0, 0);
  }
  window.addEventListener('hashchange', () => autenticado() && document.getElementById('vista') && ruta());

  const cabecera = (titulo, texto, acciones = '') =>
    `<div class="cabecera"><div class="titulo-seccion"><h1>${titulo}</h1><p>${texto}</p></div><div class="acciones">${acciones}</div></div>`;

  /* =========================================================
     OPERADORES
     ========================================================= */
  const resumenHorario = (op) => {
    const hs = TV.calc.horariosEn(op, hoy());
    if (!hs.length) return '<span class="vacio">Sin horario</span>';
    return ORDEN_DIAS.filter((d) => hs.some((h) => h.dia === d))
      .map((d) => `<div><strong>${DIAS[d]}</strong> ${hs.filter((h) => h.dia === d).sort((a, b) => aMin(a.inicio) - aMin(b.inicio)).map((h) => `${h.inicio}–${h.fin}`).join(' · ')}</div>`)
      .join('');
  };

  function vistaOperadores(main) {
    const ops = TV.db.get().operadores.slice().sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
    main.innerHTML =
      cabecera('Operadores', 'Alta y registro del personal operador del Control Maestro.', `<button class="btn btn--primario" id="o-alta" type="button">${ui.icono('mas')} Alta de operador</button>`) +
      `<section class="tarjeta"><div class="tabla-envoltura">${
        ops.length
          ? `<table class="tabla">
          <thead><tr><th>Nombre</th><th>Expediente</th><th>Carrera</th><th class="num">Edad</th><th>Horario</th><th>Huella</th><th><span class="solo-lectores">Acciones</span></th></tr></thead>
          <tbody>${ops
            .map(
              (o) => `<tr>
              <td class="nombre">${esc(o.nombre)}</td>
              <td>${esc(o.expediente)}</td>
              <td>${esc(o.carrera)}</td>
              <td class="num">${edad(o.nacimiento)}</td>
              <td class="horario">${resumenHorario(o)}</td>
              <td>${o.huella ? '<span class="insignia insignia--ok">Registrada</span>' : '<span class="insignia insignia--warn">Pendiente</span>'}</td>
              <td><div class="acciones" style="flex-wrap: nowrap">
                <button class="btn btn--secundario btn--chico" data-editar="${o.id}" type="button">${ui.icono('editar')} Datos</button>
                <button class="btn btn--secundario btn--chico" data-horarios="${o.id}" type="button">${ui.icono('reloj')} Horarios</button>
              </div></td></tr>`
            )
            .join('')}</tbody></table>`
          : '<div class="tarjeta__cuerpo"><p class="vacio vacio--caja">Aún no hay operadores. Usa “Alta de operador” para registrar al primero.</p></div>'
      }</div></section>`;

    main.querySelector('#o-alta').addEventListener('click', () => abrirOperador());
    main.querySelectorAll('[data-editar]').forEach((b) => b.addEventListener('click', () => abrirOperador(TV.db.operador(b.dataset.editar))));
    main.querySelectorAll('[data-horarios]').forEach((b) => b.addEventListener('click', () => abrirHorarios(TV.db.operador(b.dataset.horarios))));
  }

  // Editor de turnos reutilizado en el alta y en "Horarios"
  function editorHorarios(inicial) {
    const nodo = document.createElement('div');
    nodo.className = 'turnos';
    const agregar = (h = { dia: 1, inicio: '07:00', fin: '13:00' }) => {
      const f = document.createElement('div');
      f.className = 'turno';
      f.innerHTML = `
        <label class="campo"><span class="campo__etiqueta">Día</span>
          <select data-dia>${ORDEN_DIAS.map((d) => `<option value="${d}" ${d === h.dia ? 'selected' : ''}>${DIAS[d]}</option>`).join('')}</select></label>
        <label class="campo"><span class="campo__etiqueta">Entrada</span><input type="time" data-ini value="${h.inicio}" required /></label>
        <label class="campo"><span class="campo__etiqueta">Salida</span><input type="time" data-fin value="${h.fin}" required /></label>
        <button type="button" class="btn btn--texto btn--chico" data-quitar aria-label="Quitar turno">${ui.icono('x')}</button>`;
      f.querySelector('[data-quitar]').addEventListener('click', () => f.remove());
      nodo.append(f);
    };
    inicial.forEach(agregar);

    const leer = () =>
      [...nodo.querySelectorAll('.turno')].map((f) => ({
        dia: Number(f.querySelector('[data-dia]').value),
        inicio: f.querySelector('[data-ini]').value,
        fin: f.querySelector('[data-fin]').value,
      }));
    const validar = () => {
      const hs = leer();
      if (!hs.length) return 'Agrega al menos un turno.';
      for (const h of hs) {
        if (!h.inicio || !h.fin) return 'Completa la hora de entrada y de salida de cada turno.';
        if (aMin(h.fin) <= aMin(h.inicio)) return `En ${DIAS[h.dia]}, la hora de salida debe ser posterior a la de entrada.`;
      }
      const orden = hs.slice().sort((a, b) => a.dia - b.dia || aMin(a.inicio) - aMin(b.inicio));
      for (let i = 1; i < orden.length; i++) {
        if (orden[i].dia === orden[i - 1].dia && aMin(orden[i].inicio) < aMin(orden[i - 1].fin)) return `Hay turnos empalmados el ${DIAS[orden[i].dia].toLowerCase()}.`;
      }
      return '';
    };
    const normalizado = () => leer().sort((a, b) => ORDEN_DIAS.indexOf(a.dia) - ORDEN_DIAS.indexOf(b.dia) || aMin(a.inicio) - aMin(b.inicio));
    return { nodo, agregar, validar, leer: normalizado };
  }

  function enrolarHuella() {
    return new Promise((resolver) => {
      const n = document.createElement('div');
      n.className = 'huella';
      n.innerHTML = `
        <h2 class="huella__titulo">Registrar huella</h2>
        <div class="huella__sensor" data-s>${ui.icono('huella')}</div>
        <p class="huella__estado" data-e aria-live="polite"></p>
        <div class="acciones acciones--centro">
          <button class="btn btn--primario" data-c type="button">Simular captura</button>
          <button class="btn btn--texto" data-x type="button">Cancelar</button>
        </div>`;
      const m = ui.modal(n, { ancho: '28rem', cerrable: false });
      let capturas = 0;
      const e = n.querySelector('[data-e]');
      const texto = () => (e.textContent = `Captura ${capturas + 1} de 3: coloca y retira el dedo en el sensor`);
      texto();
      n.querySelector('[data-x]').addEventListener('click', () => {
        m.cerrar();
        resolver(false);
      });
      n.querySelector('[data-c]').addEventListener('click', () => {
        capturas++;
        if (capturas < 3) return texto();
        n.querySelector('[data-s]').className = 'huella__sensor huella__sensor--ok';
        e.textContent = 'Huella registrada';
        n.querySelectorAll('button').forEach((b) => (b.disabled = true));
        setTimeout(() => {
          m.cerrar();
          resolver(true);
        }, 600);
      });
    });
  }

  function abrirOperador(op) {
    const nuevo = !op;
    let huella = op ? op.huella : false;
    const horarios = nuevo ? editorHorarios([{ dia: 1, inicio: '07:00', fin: '13:00' }]) : null;

    const form = document.createElement('form');
    form.noValidate = true;
    form.innerHTML = `
      <div class="modal__cab"><h2>${nuevo ? 'Alta de operador' : 'Datos del operador'}</h2>
        <button type="button" class="btn btn--texto btn--chico" data-cancelar aria-label="Cerrar">${ui.icono('x')}</button></div>
      <div class="modal__cuerpo">
        <label class="campo" data-campo="nombre"><span class="campo__etiqueta">Nombre completo <span class="req">*</span></span>
          <input type="text" name="nombre" maxlength="120" autocomplete="off" value="${esc(op?.nombre)}" /><span class="campo__error" hidden></span></label>
        <div class="rejilla">
          <label class="campo" data-campo="nacimiento"><span class="campo__etiqueta">Fecha de nacimiento <span class="req">*</span></span>
            <input type="date" name="nacimiento" max="${hoy()}" value="${op?.nacimiento || ''}" /><span class="campo__error" hidden></span></label>
          <label class="campo" data-campo="expediente"><span class="campo__etiqueta">Expediente <span class="req">*</span></span>
            <input type="text" name="expediente" maxlength="20" autocomplete="off" value="${esc(op?.expediente)}" /><span class="campo__error" hidden></span></label>
        </div>
        <label class="campo" data-campo="carrera"><span class="campo__etiqueta">Carrera <span class="req">*</span></span>
          <input type="text" name="carrera" maxlength="100" autocomplete="off" value="${esc(op?.carrera)}" /><span class="campo__error" hidden></span></label>
        <div class="campo"><span class="campo__etiqueta">Huella biométrica</span>
          <div class="huella-estado"><span class="insignia" data-hs></span>
            <button type="button" class="btn btn--secundario btn--chico" data-huella>${ui.icono('huella')} <span data-ht></span></button></div></div>
        ${
          nuevo
            ? `<div class="campo" data-campo="horarios"><span class="campo__etiqueta">Horario que estará en turno <span class="req">*</span></span>
                <div data-contenedor></div>
                <div><button type="button" class="btn btn--secundario btn--chico" data-agregar>${ui.icono('mas')} Agregar turno</button></div>
                <span class="campo__ayuda">Ej. lunes de 07:00 a 13:00 y miércoles de 17:00 a 21:00.</span>
                <span class="campo__error" hidden></span></div>`
            : ''
        }
      </div>
      <div class="modal__pie">
        <button type="button" class="btn btn--secundario" data-cancelar>Cancelar</button>
        <button type="submit" class="btn btn--primario">${nuevo ? 'Registrar operador' : 'Guardar cambios'}</button>
      </div>`;
    const m = ui.modal(form, { ancho: '40rem', cerrable: false });
    if (nuevo) {
      form.querySelector('[data-contenedor]').append(horarios.nodo);
      form.querySelector('[data-agregar]').addEventListener('click', () => horarios.agregar());
    }

    const pintarHuella = () => {
      const s = form.querySelector('[data-hs]');
      s.className = `insignia ${huella ? 'insignia--ok' : 'insignia--warn'}`;
      s.textContent = huella ? 'Registrada' : 'Pendiente';
      form.querySelector('[data-ht]').textContent = huella ? 'Volver a capturar' : 'Registrar huella';
    };
    pintarHuella();
    form.querySelector('[data-huella]').addEventListener('click', async () => {
      if (await enrolarHuella()) {
        huella = true;
        pintarHuella();
      }
    });
    form.querySelectorAll('[data-cancelar]').forEach((b) => b.addEventListener('click', () => m.cerrar()));

    const campo = (n) => form.querySelector(`[data-campo="${n}"]`);
    const error = (n, texto) => {
      const c = campo(n);
      c.classList.toggle('campo--invalido', !!texto);
      const e = c.querySelector('.campo__error');
      e.hidden = !texto;
      e.textContent = texto || '';
      return !!texto;
    };

    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const exp = form.expediente.value.trim();
      const duplicado = TV.db.get().operadores.some((o) => o.expediente.toLowerCase() === exp.toLowerCase() && o.id !== op?.id);
      let mal = false;
      mal = error('nombre', form.nombre.value.trim().split(/\s+/).filter(Boolean).length >= 2 ? '' : 'Escribe el nombre completo (nombre y apellido).') || mal;
      mal = error('nacimiento', !form.nacimiento.value ? 'Indica la fecha de nacimiento.' : form.nacimiento.value > hoy() ? 'La fecha no puede ser futura.' : edad(form.nacimiento.value) < 15 ? 'Revisa la fecha de nacimiento.' : '') || mal;
      mal = error('expediente', !exp ? 'Indica el expediente.' : duplicado ? 'Ya existe un operador con ese expediente.' : '') || mal;
      mal = error('carrera', form.carrera.value.trim() ? '' : 'Indica la carrera.') || mal;
      if (nuevo) mal = error('horarios', horarios.validar()) || mal;
      if (mal) return form.querySelector('.campo--invalido input')?.focus();

      const datos = { nombre: form.nombre.value.trim().replace(/\s+/g, ' '), nacimiento: form.nacimiento.value, expediente: exp, carrera: form.carrera.value.trim(), huella };
      if (nuevo) {
        TV.db.get().operadores.push({ id: TV.db.uid(), ...datos, alta: hoy(), versionesHorario: [{ desde: hoy(), horarios: horarios.leer() }] });
      } else {
        Object.assign(op, datos);
      }
      TV.db.guardar();
      m.cerrar();
      ui.toast(nuevo ? 'Operador registrado' : 'Cambios guardados');
      ruta();
    });
    form.nombre.focus();
  }

  function abrirHorarios(op) {
    const ed = editorHorarios(TV.calc.horariosEn(op, hoy()));
    const nodo = document.createElement('form');
    nodo.noValidate = true;
    nodo.innerHTML = `
      <div class="modal__cab"><h2>Horario de ${esc(op.nombre)}</h2>
        <button type="button" class="btn btn--texto btn--chico" data-cancelar aria-label="Cerrar">${ui.icono('x')}</button></div>
      <div class="modal__cuerpo">
        <div data-contenedor></div>
        <div><button type="button" class="btn btn--secundario btn--chico" data-agregar>${ui.icono('mas')} Agregar turno</button></div>
        <p class="campo__error" data-error role="alert" hidden></p>
        <p class="regla">El nuevo horario aplica a partir de hoy. Las asistencias y faltas de fechas anteriores se siguen calculando con el horario que tenía vigente.</p>
      </div>
      <div class="modal__pie">
        <button type="button" class="btn btn--secundario" data-cancelar>Cancelar</button>
        <button type="submit" class="btn btn--primario">Guardar horario</button>
      </div>`;
    nodo.querySelector('[data-contenedor]').append(ed.nodo);
    const m = ui.modal(nodo, { ancho: '38rem', cerrable: false });
    nodo.querySelector('[data-agregar]').addEventListener('click', () => ed.agregar());
    nodo.querySelectorAll('[data-cancelar]').forEach((b) => b.addEventListener('click', () => m.cerrar()));
    nodo.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const e = ed.validar();
      const caja = nodo.querySelector('[data-error]');
      caja.hidden = !e;
      caja.textContent = e;
      if (e) return;
      const v = op.versionesHorario;
      const nueva = { desde: hoy(), horarios: ed.leer() };
      if (v[v.length - 1].desde === nueva.desde) v[v.length - 1] = nueva;
      else v.push(nueva);
      TV.db.guardar();
      m.cerrar();
      ui.toast('Horario actualizado');
      ruta();
    });
  }

  /* =========================================================
     REPORTES
     ========================================================= */
  const PERIODOS = [
    ['', 'Personalizado'],
    ['hoy', 'Hoy'],
    ['7d', 'Últimos 7 días'],
    ['30d', 'Últimos 30 días'],
    ['mes', 'Este mes'],
    ['mesant', 'Mes anterior'],
    ['q1', 'Primera quincena (1–15)'],
    ['q2', 'Segunda quincena (16–fin)'],
    ['anio', 'Este año'],
  ];
  function rangoPeriodo(id) {
    const d = new Date();
    const a = d.getFullYear();
    const m = d.getMonth();
    const f = (y, mes, dia) => ymd(new Date(y, mes, dia));
    return {
      hoy: [hoy(), hoy()],
      '7d': [f(a, m, d.getDate() - 6), hoy()],
      '30d': [f(a, m, d.getDate() - 29), hoy()],
      mes: [f(a, m, 1), hoy()],
      mesant: [f(a, m - 1, 1), f(a, m, 0)],
      q1: [f(a, m, 1), f(a, m, 15)],
      q2: [f(a, m, 16), f(a, m + 1, 0)],
      anio: [f(a, 0, 1), hoy()],
    }[id];
  }

  const filtroFechas = () => `
    <label class="campo"><span class="campo__etiqueta">Periodo</span>
      <select id="f-preset">${PERIODOS.map(([v, t]) => `<option value="${v}" ${v === F.preset ? 'selected' : ''}>${t}</option>`).join('')}</select></label>
    <label class="campo"><span class="campo__etiqueta">Fecha inicial</span><input type="date" id="f-desde" value="${F.desde}" /></label>
    <label class="campo"><span class="campo__etiqueta">Fecha final</span><input type="date" id="f-hasta" value="${F.hasta}" /></label>`;

  const periodoValido = () => (F.desde && F.hasta && F.desde <= F.hasta ? '' : 'La fecha inicial debe ser anterior o igual a la final.');
  const errorHtml = (t) => `<div class="tarjeta__cuerpo"><p class="campo__error" role="alert">${esc(t)}</p></div>`;
  const periodoTxt = () => `Periodo: del ${fmtFecha(F.desde)} al ${fmtFecha(F.hasta)}`;
  const BOTON_PDF = `<button class="btn btn--secundario" id="r-pdf" type="button">${ui.icono('imprimir')} Generar PDF</button>`;

  const ESTADOS = {
    asistencia: ['ok', 'Asistencia'],
    retardo: ['warn', 'Retardo'],
    incompleto: ['warn', 'Turno incompleto'],
    falta: ['err', 'Falta'],
    'en-curso': ['info', 'En curso'],
    'sin-salida': ['neutra', 'Sin salida'],
    pendiente: ['neutra', 'Pendiente'],
  };
  const insignia = (e) => `<span class="insignia insignia--${ESTADOS[e][0]}">${ESTADOS[e][1]}</span>`;
  const vacioTabla = (t) => `<p class="vacio">${t}</p>`;

  /* ---------- Tabla de asistencias ---------- */
  function htmlAsistencia() {
    const filas = TV.db
      .get()
      .operadores.slice()
      .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'))
      .map((o) => ({ o, r: TV.calc.resumen(o, F.desde, F.hasta) }));
    if (!filas.length) return vacioTabla('No hay operadores registrados.');
    return `<table class="tabla">
      <thead><tr><th>Nombre completo</th><th class="num">Edad</th><th>Expediente</th><th>Carrera</th>
        <th class="num">Asistencias</th><th class="num">Faltas</th><th class="num">Retardos</th><th class="num">Turnos incompletos</th><th class="num">Justificadas</th></tr></thead>
      <tbody>${filas
        .map(
          ({ o, r }) => `<tr>
          <td class="nombre"><a href="#/individual?op=${o.id}">${esc(o.nombre)}</a></td>
          <td class="num">${edad(o.nacimiento)}</td><td>${esc(o.expediente)}</td><td>${esc(o.carrera)}</td>
          <td class="num">${r.asistencias}</td><td class="num">${r.faltas}</td><td class="num">${r.retardos}</td><td class="num">${r.incompletos}</td><td class="num">${r.justificadas}</td></tr>`
        )
        .join('')}</tbody></table>`;
  }

  function vistaAsistencia(main) {
    main.innerHTML =
      cabecera('Tabla de asistencias', 'Resumen del personal operador en el periodo seleccionado.', BOTON_PDF) +
      `<section class="tarjeta"><div class="tarjeta__cuerpo"><div class="filtros">${filtroFechas()}</div></div></section>
       <section class="tarjeta"><div class="tabla-envoltura" id="r-cuerpo"></div></section>
       <section class="regla">
         <strong>Asistencia:</strong> entrada y salida registradas, llegando hasta ${TV.CFG.toleranciaRetardoMin} min después de la hora programada.
         <strong>Retardo:</strong> entrada entre ${TV.CFG.toleranciaRetardoMin} y ${TV.CFG.limiteEntradaMin} min después de la hora programada.
         <strong>Falta:</strong> no registró entrada, o llegó pasados ${TV.CFG.limiteEntradaMin} min (su entrada se registra, pero con falta).
         <strong>Turno incompleto:</strong> retardo y salida antes del horario final.
         <strong>Justificadas:</strong> turnos que el administrador justificó; ya no suman como falta, retardo ni tiempo faltante.
       </section>`;
    const pintar = () => {
      const e = periodoValido();
      main.querySelector('#r-cuerpo').innerHTML = e ? errorHtml(e) : htmlAsistencia();
      main.querySelector('#r-pdf').disabled = !!e;
    };
    enlazarFechas(main, pintar);
    main.querySelector('#r-pdf').addEventListener('click', () => ui.imprimir({ titulo: 'Tabla de asistencias', meta: periodoTxt(), html: htmlAsistencia() }));
    pintar();
  }

  // Periodo rápido + fechas manuales: tocar una fecha vuelve el periodo a "Personalizado"
  function enlazarFechas(main, pintar) {
    const preset = main.querySelector('#f-preset');
    const desde = main.querySelector('#f-desde');
    const hasta = main.querySelector('#f-hasta');
    preset.addEventListener('change', () => {
      F.preset = preset.value;
      if (F.preset) [F.desde, F.hasta] = rangoPeriodo(F.preset);
      desde.value = F.desde;
      hasta.value = F.hasta;
      pintar();
    });
    const manual = (campo, clave) => () => {
      F[clave] = campo.value;
      F.preset = '';
      preset.value = '';
      pintar();
    };
    desde.addEventListener('change', manual(desde, 'desde'));
    hasta.addEventListener('change', manual(hasta, 'hasta'));
  }

  /* ---------- Registro de asistencia (un día, todo el personal con turno) ---------- */
  function filasPase(fecha) {
    const ahora = Date.now();
    return TV.db
      .get()
      .operadores.flatMap((op) => TV.calc.resumen(op, fecha, fecha, ahora, { pendientes: true }).filas.map((f) => ({ op, f })))
      .sort((a, b) => a.f.iniTs - b.f.iniTs || a.op.nombre.localeCompare(b.op.nombre, 'es'));
  }

  function htmlPase(fecha, acciones = false) {
    const filas = filasPase(fecha);
    if (!filas.length) return vacioTabla('Ningún operador tiene turno programado este día.');
    const cuenta = (fn) => filas.filter(({ f }) => fn(f)).length;
    const dato = (v, e, cls = '') => `<div class="dato ${cls}"><div class="dato__valor">${v}</div><div class="dato__etiqueta">${e}</div></div>`;
    const faltas = cuenta((f) => f.estado === 'falta' && !f.justificada);
    const retardos = cuenta((f) => f.retardo && !f.justificada);
    const pendientes = cuenta((f) => f.estado === 'pendiente');
    const presentes = cuenta((f) => ['asistencia', 'retardo', 'incompleto', 'en-curso', 'sin-salida'].includes(f.estado));
    return `
      <div class="resumen">
        ${dato(filas.length, 'Turnos del día')}
        ${dato(presentes, 'Presentes')}
        ${dato(retardos, 'Retardos', retardos ? 'dato--warn' : '')}
        ${dato(faltas, 'Faltas', faltas ? 'dato--err' : '')}
        ${dato(pendientes, 'Pendientes')}
        ${dato(cuenta((f) => f.justificada), 'Justificadas')}
      </div>
      <div class="tabla-envoltura"><table class="tabla">
        <thead><tr><th>Operador</th><th>Expediente</th><th>Turno</th><th>Entrada</th><th>Salida</th><th>Estado</th>${acciones ? '<th><span class="solo-lectores">Acciones</span></th>' : ''}</tr></thead>
        <tbody>${filas
          .map(
            ({ op, f }) => `<tr>
            <td class="nombre">${esc(op.nombre)}</td><td>${esc(op.expediente)}</td><td>${f.turno.inicio}–${f.turno.fin}</td>
            <td>${f.entradaTs ? fmtHora(f.entradaTs) : '–'}</td><td>${f.salidaTs ? fmtHora(f.salidaTs) : '–'}</td>
            <td>${insignia(f.estado)}${f.faltaTardia ? ' <span class="regla">entró ' + durCorta((f.entradaTs - f.iniTs) / TV.MIN) + ' tarde</span>' : ''}${f.retardo && f.estado !== 'retardo' && f.estado !== 'incompleto' ? ' ' + insignia('retardo') : ''}${f.justificada ? ' <span class="insignia insignia--info">Justificada</span>' : ''}${marcaEditado(f)}${f.justificada ? `<div class="regla">${esc(f.motivo)}</div>` : ''}</td>
            ${acciones ? `<td>${botonesTurno(op.id, f)}</td>` : ''}</tr>`
          )
          .join('')}</tbody></table></div>`;
  }

  function vistaPase(main) {
    const mover = (dias) => {
      const d = parseYmd(F.pase);
      d.setDate(d.getDate() + dias);
      F.pase = ymd(d);
    };
    const nombreDia = () => DIAS[parseYmd(F.pase).getDay()];
    main.innerHTML =
      cabecera('Registro de asistencia', 'Asistencia del día de todo el personal con turno programado.', BOTON_PDF) +
      `<section class="tarjeta"><div class="tarjeta__cuerpo"><div class="filtros">
         <label class="campo"><span class="campo__etiqueta">Fecha</span><input type="date" id="p-fecha" value="${F.pase}" /></label>
         <div class="acciones" style="align-self: end">
           <button class="btn btn--secundario" id="p-ant" type="button">‹ Día anterior</button>
           <button class="btn btn--secundario" id="p-hoy" type="button">Hoy</button>
           <button class="btn btn--secundario" id="p-sig" type="button">Día siguiente ›</button>
         </div>
         <p class="regla" id="p-dia" style="align-self: end"></p>
       </div></div></section>
       <section class="tarjeta"><div class="tarjeta__cuerpo" id="r-cuerpo"></div></section>`;
    const pintar = () => {
      main.querySelector('#p-fecha').value = F.pase;
      main.querySelector('#p-dia').textContent = nombreDia();
      main.querySelector('#r-cuerpo').innerHTML = F.pase ? htmlPase(F.pase, true) : errorHtml('Selecciona una fecha.');
      main.querySelector('#r-pdf').disabled = !F.pase;
    };
    main.querySelector('#p-fecha').addEventListener('change', (e) => ((F.pase = e.target.value), pintar()));
    main.querySelector('#p-ant').addEventListener('click', () => (mover(-1), pintar()));
    main.querySelector('#p-sig').addEventListener('click', () => (mover(1), pintar()));
    main.querySelector('#p-hoy').addEventListener('click', () => ((F.pase = hoy()), pintar()));
    main.querySelector('#r-cuerpo').addEventListener('click', (ev) => accionTurno(ev, pintar));
    main.querySelector('#r-pdf').addEventListener('click', () => ui.imprimir({ titulo: 'Registro de asistencia', meta: `Fecha: ${nombreDia()} ${fmtFecha(F.pase)}`, html: htmlPase(F.pase) }));
    pintar();
  }

  /* ---------- Reporte individual ---------- */
  const CONCEPTO = (f) => (f.estado === 'falta' ? (f.ajuste ? 'Falta (cambio manual)' : f.entradaTs ? 'Falta (llegada tardía)' : 'Falta') : f.incompleto ? 'Turno incompleto' : f.retardo ? 'Retardo' : 'Tiempo faltante');
  // Acciones por turno: siempre "Editar"; "Justificar" solo si hay falta, retardo o tiempo faltante
  const botonesTurno = (opId, f) => {
    const k = `${opId}|${f.fecha}|${f.turno.inicio}`;
    const justificar = f.justificada
      ? `<button class="btn btn--texto btn--chico" type="button" data-quitar-just="${f.justId}">Quitar justificación</button>`
      : f.justificable
        ? `<button class="btn btn--secundario btn--chico" type="button" data-justificar="${k}">Justificar</button>`
        : '';
    return `<div class="acciones acciones--fila">${justificar}<button class="btn btn--secundario btn--chico" type="button" data-editar="${k}">${ui.icono('editar')} Editar</button></div>`;
  };
  const marcaEditado = (f) => (f.editado ? ` <span class="insignia insignia--neutra" title="${esc(f.edicionMotivo)}">Editado</span>` : '');

  async function accionTurno(ev, repintar) {
    const just = ev.target.closest('[data-justificar]');
    const edit = ev.target.closest('[data-editar]');
    const quitar = ev.target.closest('[data-quitar-just]');
    if (just || edit) {
      const [opId, fecha, inicio] = (just || edit).dataset[just ? 'justificar' : 'editar'].split('|');
      const op = TV.db.operador(opId);
      if (await (just ? abrirJustificacion(op, fecha, inicio) : abrirEdicion(op, fecha, inicio))) repintar();
    } else if (quitar) {
      const ok = await ui.confirmar({ titulo: 'Quitar justificación', mensaje: 'El turno volverá a contar como falta, retardo o tiempo faltante según corresponda.', aceptar: 'Quitar' });
      if (!ok) return;
      const lista = TV.db.get().justificaciones;
      lista.splice(lista.findIndex((j) => j.id === quitar.dataset.quitarJust), 1);
      TV.db.guardar();
      ui.toast('Justificación quitada');
      repintar();
    }
  }

  function htmlIndividual(op, acciones = false) {
    const r = TV.calc.resumen(op, F.desde, F.hasta);
    const cumplio = r.filas.filter((f) => ['asistencia', 'retardo', 'incompleto'].includes(f.estado));
    const h = (ts) => (ts ? fmtHora(ts) : '–');
    const faltas = r.filas.filter((f) => f.estado === 'falta' && !f.justificada);
    const retardos = r.filas.filter((f) => f.retardo && !f.justificada);
    const incompletos = r.filas.filter((f) => f.incompleto && !f.justificada);
    const justificadas = r.filas.filter((f) => f.justificada);
    const dato = (v, e, cls = '') => `<div class="dato ${cls}"><div class="dato__valor">${v}</div><div class="dato__etiqueta">${e}</div></div>`;
    const dia = (f) => DIAS[parseYmd(f.fecha).getDay()];
    const tabla = (cols, filas) => `<div class="tabla-envoltura"><table class="tabla"><thead><tr>${cols.map((c) => `<th${c.num ? ' class="num"' : ''}>${c.t}</th>`).join('')}</tr></thead><tbody>${filas}</tbody></table></div>`;
    const seccion = (t, n, cuerpo) => `<div class="seccion-rep"><h3>${t} (${n})</h3>${n ? cuerpo : vacioTabla('Sin registros en el periodo.')}</div>`;

    return `
      <div class="resumen">
        ${dato(r.asistencias, 'Asistencias')}
        ${dato(r.faltas, 'Faltas', r.faltas ? 'dato--err' : '')}
        ${dato(r.retardos, 'Retardos', r.retardos ? 'dato--warn' : '')}
        ${dato(r.incompletos, 'Turnos incompletos', r.incompletos ? 'dato--warn' : '')}
        ${dato(durCorta(r.faltanteMin), 'Tiempo total por cumplir', r.faltanteMin ? 'dato--err' : '')}
        ${dato(r.justificadas, 'Justificadas')}
      </div>
      ${r.sinSalida ? `<p class="regla">${r.sinSalida} turno(s) con entrada pero sin salida registrada: no se cuentan como asistencia ni suman tiempo por cumplir hasta que se aclaren.</p>` : ''}
      ${seccion('Asistencias', cumplio.length, tabla([{ t: 'Fecha' }, { t: 'Turno' }, { t: 'Entrada' }, { t: 'Salida' }], cumplio.map((f) => `<tr><td>${fmtFecha(f.fecha)}</td><td>${f.turno.inicio}–${f.turno.fin}</td><td>${h(f.entradaTs)}</td><td>${h(f.salidaTs)}</td></tr>`).join('')))}
      ${seccion('Faltas', faltas.length, `<ul class="lista-fechas">${faltas.map((f) => `<li>${fmtFecha(f.fecha)} · ${f.turno.inicio}–${f.turno.fin}${f.ajuste ? ' (cambio manual)' : f.entradaTs ? ` (llegó a las ${fmtHora(f.entradaTs)})` : ''}</li>`).join('')}</ul>`)}
      ${seccion('Retardos', retardos.length, tabla([{ t: 'Fecha' }, { t: 'Entrada' }, { t: 'Salida' }, { t: 'Retraso', num: 1 }], retardos.map((f) => `<tr><td>${fmtFecha(f.fecha)}</td><td>${h(f.entradaTs)}</td><td>${h(f.salidaTs)}</td><td class="num">${f.entradaTs ? durCorta((f.entradaTs - f.iniTs) / TV.MIN) : '–'}</td></tr>`).join('')))}
      ${seccion('Turnos incompletos', incompletos.length, tabla([{ t: 'Fecha' }, { t: 'Entrada' }, { t: 'Salida' }, { t: 'Fin programado' }], incompletos.map((f) => `<tr><td>${fmtFecha(f.fecha)}</td><td>${fmtHora(f.entradaTs)}</td><td>${fmtHora(f.salidaTs)}</td><td>${f.turno.fin}</td></tr>`).join('')))}
      ${seccion('Justificadas', justificadas.length, tabla([{ t: 'Fecha' }, { t: 'Turno' }, { t: 'Concepto' }, { t: 'Motivo' }], justificadas.map((f) => `<tr><td>${fmtFecha(f.fecha)}</td><td>${f.turno.inicio}–${f.turno.fin}</td><td>${esc(CONCEPTO(f))}</td><td>${esc(f.motivo)}</td></tr>`).join('')))}
      ${seccion(
        'Detalle de horas por turno',
        r.filas.length,
        tabla(
          [{ t: 'Fecha' }, { t: 'Turno' }, { t: 'Entrada' }, { t: 'Salida' }, { t: 'Horas en turno', num: 1 }, { t: 'Tiempo faltante', num: 1 }, { t: 'Estado' }].concat(acciones ? [{ t: '<span class="solo-lectores">Acciones</span>' }] : []),
          r.filas
            .map(
              (f) => `<tr><td>${fmtFecha(f.fecha)} <span class="regla">${dia(f)}</span></td><td>${f.turno.inicio}–${f.turno.fin}</td>
              <td>${f.entradaTs ? fmtHora(f.entradaTs) : '–'}</td><td>${f.salidaTs ? fmtHora(f.salidaTs) : '–'}</td>
              <td class="num">${f.salidaTs ? durCorta(f.trabajadoMin) : '–'}</td><td class="num">${f.estado === 'en-curso' || f.estado === 'sin-salida' ? '–' : f.faltanteMin ? durCorta(f.faltanteMin) : '0 min'}</td>
              <td>${insignia(f.estado)}${f.faltaTardia ? ' <span class="regla">entró ' + durCorta((f.entradaTs - f.iniTs) / TV.MIN) + ' tarde</span>' : ''}${f.retardo && f.estado !== 'retardo' && f.estado !== 'incompleto' && !f.faltaTardia ? ' ' + insignia('retardo') : ''}${f.justificada ? ' <span class="insignia insignia--info">Justificada</span>' : ''}${marcaEditado(f)}</td>${acciones ? `<td>${botonesTurno(op.id, f)}</td>` : ''}</tr>`
            )
            .join('')
        )
      )}
      <p class="regla">Horas en turno = hora de salida − hora de entrada. Tiempo faltante = horas programadas − horas en turno; una falta suma su turno completo.</p>`;
  }

  // Editar un turno: cambiar el estatus a mano (con un motivo opcional)
  const ESTATUS_MANUAL = [
    ['asistencia', 'Asistencia'],
    ['retardo', 'Retardo'],
    ['falta', 'Falta'],
  ];
  function abrirEdicion(op, fecha, inicio) {
    const fila = TV.calc.resumen(op, fecha, fecha, Date.now(), { pendientes: true }).filas.find((f) => f.turno.inicio === inicio);
    const ajustes = TV.db.get().ajustes;
    const previo = ajustes.find((x) => x.operadorId === op.id && x.fecha === fecha && x.turnoInicio === inicio);
    const actual = ['asistencia', 'retardo', 'falta'].includes(fila.estado) ? fila.estado : fila.estado === 'incompleto' ? 'retardo' : '';
    const form = document.createElement('form');
    form.noValidate = true;
    form.innerHTML = `
      <div class="modal__cab"><h2>Editar estatus</h2>
        <button type="button" class="btn btn--texto btn--chico" data-cancelar aria-label="Cerrar">${ui.icono('x')}</button></div>
      <div class="modal__cuerpo">
        <p><strong>${esc(op.nombre)}</strong><br />${fmtFecha(fecha)} · turno ${fila.turno.inicio}–${fila.turno.fin} · ahora: ${insignia(fila.estado)}</p>
        <fieldset class="opciones-edicion" data-campo="estatus">
          <legend class="campo__etiqueta">Estatus</legend>
          ${ESTATUS_MANUAL.map(([v, t]) => `<label class="opcion-edicion"><input type="radio" name="estatus" value="${v}" ${v === actual ? 'checked' : ''} /><span><strong>${t}</strong></span></label>`).join('')}
          ${previo ? '<label class="opcion-edicion"><input type="radio" name="estatus" value="auto" /><span><strong>Volver al estatus calculado</strong><small>Quita el cambio manual y vuelve a contar según el registro del sensor.</small></span></label>' : ''}
          <span class="campo__error" hidden></span>
        </fieldset>
        <label class="campo"><span class="campo__etiqueta">Motivo (opcional)</span>
          <textarea name="motivo" maxlength="300" placeholder="Ej. Se retiró del Control Maestro antes de terminar"></textarea></label>
      </div>
      <div class="modal__pie">
        <button type="button" class="btn btn--secundario" data-cancelar>Cancelar</button>
        <button type="submit" class="btn btn--primario">Guardar</button>
      </div>`;
    const m = ui.modal(form, { ancho: '30rem', cerrable: false });
    form.querySelectorAll('[data-cancelar]').forEach((b) => b.addEventListener('click', () => m.cerrar(false)));
    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const marcada = form.querySelector('input[name=estatus]:checked');
      const campo = form.querySelector('[data-campo="estatus"] .campo__error');
      campo.hidden = !!marcada;
      campo.textContent = marcada ? '' : 'Elige el nuevo estatus.';
      if (!marcada) return;
      const nuevo = marcada.value;
      const motivo = form.motivo.value.trim();
      if (previo) ajustes.splice(ajustes.indexOf(previo), 1);
      if (nuevo !== 'auto') ajustes.push({ id: TV.db.uid(), operadorId: op.id, fecha, turnoInicio: inicio, estado: nuevo, motivo, ts: Date.now() });
      TV.db.get().ediciones.push({ id: TV.db.uid(), operadorId: op.id, fecha, turnoInicio: inicio, antes: fila.estado, despues: nuevo, motivo, ts: Date.now() });
      TV.db.guardar();
      ui.toast(nuevo === 'auto' ? 'Estatus calculado restaurado' : `Estatus cambiado a ${ESTATUS_MANUAL.find(([v]) => v === nuevo)[1].toLowerCase()}`);
      m.cerrar(true);
    });
    (form.querySelector('input[name=estatus]:checked') || form.querySelector('input[name=estatus]')).focus();
    return m.promesa;
  }

  function abrirJustificacion(op, fecha, inicio) {
    const fila = TV.calc.resumen(op, fecha, fecha).filas.find((f) => f.turno.inicio === inicio);
    const form = document.createElement('form');
    form.noValidate = true;
    form.innerHTML = `
      <div class="modal__cab"><h2>Justificar</h2>
        <button type="button" class="btn btn--texto btn--chico" data-cancelar aria-label="Cerrar">${ui.icono('x')}</button></div>
      <div class="modal__cuerpo">
        <p><strong>${esc(CONCEPTO(fila))}</strong> de ${esc(op.nombre)}<br />${fmtFecha(fecha)} · turno ${fila.turno.inicio}–${fila.turno.fin}</p>
        <label class="campo" data-campo="motivo"><span class="campo__etiqueta">Motivo <span class="req">*</span></span>
          <textarea name="motivo" maxlength="300" placeholder="Ej. Consulta médica con comprobante"></textarea>
          <span class="campo__error" hidden></span></label>
        <p class="regla">Un turno justificado deja de contar como falta, retardo o tiempo faltante. Puedes quitar la justificación después.</p>
      </div>
      <div class="modal__pie">
        <button type="button" class="btn btn--secundario" data-cancelar>Cancelar</button>
        <button type="submit" class="btn btn--primario">Guardar justificación</button>
      </div>`;
    const m = ui.modal(form, { ancho: '34rem', cerrable: false });
    form.querySelectorAll('[data-cancelar]').forEach((b) => b.addEventListener('click', () => m.cerrar(false)));
    form.addEventListener('submit', (ev) => {
      ev.preventDefault();
      const motivo = form.motivo.value.trim();
      const c = form.querySelector('[data-campo="motivo"]');
      const e = c.querySelector('.campo__error');
      c.classList.toggle('campo--invalido', !motivo);
      e.hidden = !!motivo;
      e.textContent = motivo ? '' : 'Escribe el motivo de la justificación.';
      if (!motivo) return form.motivo.focus();
      TV.db.get().justificaciones.push({ id: TV.db.uid(), operadorId: op.id, fecha, turnoInicio: inicio, concepto: CONCEPTO(fila), motivo, creadoTs: Date.now() });
      TV.db.guardar();
      ui.toast('Justificación guardada');
      m.cerrar(true);
    });
    form.motivo.focus();
    return m.promesa;
  }

  function vistaIndividual(main) {
    const ops = TV.db.get().operadores.slice().sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
    if (!TV.db.operador(F.op)) F.op = ops[0]?.id || '';
    main.innerHTML =
      cabecera('Reporte individual', 'Asistencias, faltas, retardos y tiempo por cumplir de una persona.', BOTON_PDF) +
      `<section class="tarjeta"><div class="tarjeta__cuerpo"><div class="filtros">
         <label class="campo"><span class="campo__etiqueta">Operador</span>
           <select id="f-op">${ops.map((o) => `<option value="${o.id}" ${o.id === F.op ? 'selected' : ''}>${esc(o.nombre)}</option>`).join('')}</select></label>
         ${filtroFechas()}
       </div></div></section>
       <section class="tarjeta"><div class="tarjeta__cuerpo" id="r-cuerpo"></div></section>`;

    const meta = (op) => `${esc(op.nombre)} · Expediente ${esc(op.expediente)} · ${esc(op.carrera)} · ${edad(op.nacimiento)} años<br />${periodoTxt()}`;
    const pintar = () => {
      const op = TV.db.operador(F.op);
      const e = !op ? 'No hay operadores registrados.' : periodoValido();
      main.querySelector('#r-cuerpo').innerHTML = e ? errorHtml(e) : htmlIndividual(op, true);
      main.querySelector('#r-pdf').disabled = !!e;
    };
    main.querySelector('#r-cuerpo').addEventListener('click', (ev) => accionTurno(ev, pintar));
    enlazarFechas(main, pintar);
    main.querySelector('#f-op')?.addEventListener('change', (e) => ((F.op = e.target.value), pintar()));
    main.querySelector('#r-pdf').addEventListener('click', () => {
      const op = TV.db.operador(F.op);
      ui.imprimir({ titulo: 'Reporte individual de asistencia', meta: meta(op), html: htmlIndividual(op) });
    });
    pintar();
  }

  /* ---------- Incidencias ---------- */
  function incidenciasFiltradas() {
    const [d, h] = F.modoFecha === 'fecha' ? [F.fecha, F.fecha] : [F.desde, F.hasta];
    return TV.db
      .get()
      .incidencias.filter((i) => i.fecha >= d && i.fecha <= h && (!F.tipo || i.tipo === F.tipo) && (!F.operador || i.operadorId === F.operador))
      .sort((a, b) => b.registradoTs - a.registradoTs);
  }

  function htmlIncidencias() {
    const lista = incidenciasFiltradas();
    if (!lista.length) return vacioTabla('No hay incidencias con los filtros seleccionados.');
    return `<table class="tabla">
      <thead><tr><th>Registrada</th><th>Fecha</th><th>Hora</th><th>Programa</th><th class="num">Duración</th><th>Tipo</th><th>Observación</th><th>Operador</th></tr></thead>
      <tbody>${lista
        .map(
          (i) => `<tr><td>${TV.util.fmtFechaHora(i.registradoTs)}</td><td>${fmtFecha(i.fecha)}</td><td>${i.hora}</td>
          <td>${esc(i.programa) || '–'}</td><td class="num">${i.duracionMin == null ? '–' : durCorta(i.duracionMin)}</td>
          <td>${esc(tipoNombre(i.tipo))}</td><td class="obs">${esc(i.observacion)}</td>
          <td>${esc(TV.db.operador(i.operadorId)?.nombre || '–')}</td></tr>`
        )
        .join('')}</tbody></table>`;
  }

  function vistaIncidencias(main) {
    const ops = TV.db.get().operadores.slice().sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
    main.innerHTML =
      cabecera('Incidencias', 'Consulta por fecha, tipo de incidencia u operador que realizó el registro.', BOTON_PDF) +
      `<section class="tarjeta"><div class="tarjeta__cuerpo"><div class="filtros">
         <div class="campo"><span class="campo__etiqueta">Consultar por</span>
           <div class="opciones">
             <label><input type="radio" name="modo" value="rango" ${F.modoFecha === 'rango' ? 'checked' : ''} /> Rango</label>
             <label><input type="radio" name="modo" value="fecha" ${F.modoFecha === 'fecha' ? 'checked' : ''} /> Fecha específica</label>
           </div></div>
         <div id="f-rango" class="filtros" style="display: contents" ${F.modoFecha === 'fecha' ? 'hidden' : ''}>${filtroFechas()}</div>
         <label class="campo" id="f-especifica" ${F.modoFecha === 'rango' ? 'hidden' : ''}><span class="campo__etiqueta">Fecha</span><input type="date" id="f-fecha" value="${F.fecha}" /></label>
         <label class="campo"><span class="campo__etiqueta">Tipo de incidencia</span>
           <select id="f-tipo"><option value="">Todos</option>${TV.TIPOS.map((t) => `<option value="${t.id}" ${t.id === F.tipo ? 'selected' : ''}>${esc(t.nombre)}</option>`).join('')}</select></label>
         <label class="campo"><span class="campo__etiqueta">Operador que registró</span>
           <select id="f-operador"><option value="">Todos</option>${ops.map((o) => `<option value="${o.id}" ${o.id === F.operador ? 'selected' : ''}>${esc(o.nombre)}</option>`).join('')}</select></label>
       </div></div></section>
       <section class="tarjeta"><div class="tarjeta__cuerpo"><p class="regla" id="r-conteo"></p></div><div class="tabla-envoltura" id="r-cuerpo"></div></section>`;

    const metaTxt = () => {
      const f = F.modoFecha === 'fecha' ? `Fecha: ${fmtFecha(F.fecha)}` : periodoTxt();
      const t = F.tipo ? ` · Tipo: ${esc(tipoNombre(F.tipo))}` : '';
      const o = F.operador ? ` · Operador: ${esc(TV.db.operador(F.operador)?.nombre)}` : '';
      return f + t + o;
    };
    const pintar = () => {
      const e = F.modoFecha === 'rango' ? periodoValido() : F.fecha ? '' : 'Selecciona una fecha.';
      main.querySelector('#r-cuerpo').innerHTML = e ? errorHtml(e) : htmlIncidencias();
      main.querySelector('#r-conteo').textContent = e ? '' : `${incidenciasFiltradas().length} incidencia(s) encontradas`;
      main.querySelector('#r-pdf').disabled = !!e;
    };
    enlazarFechas(main, pintar);
    main.querySelector('#f-fecha').addEventListener('change', (e) => ((F.fecha = e.target.value), pintar()));
    main.querySelector('#f-tipo').addEventListener('change', (e) => ((F.tipo = e.target.value), pintar()));
    main.querySelector('#f-operador').addEventListener('change', (e) => ((F.operador = e.target.value), pintar()));
    main.querySelectorAll('input[name=modo]').forEach((r) =>
      r.addEventListener('change', () => {
        F.modoFecha = r.value;
        main.querySelector('#f-rango').hidden = r.value === 'fecha';
        main.querySelector('#f-especifica').hidden = r.value === 'rango';
        pintar();
      })
    );
    main.querySelector('#r-pdf').addEventListener('click', () => ui.imprimir({ titulo: 'Reporte de incidencias', meta: metaTxt(), html: htmlIncidencias(), apaisado: true }));
    pintar();
  }

  /* ---------- Arranque ---------- */
  sensor.montarSimulador('admin');
  if (autenticado()) {
    sensor.visible(false);
    armarShell();
  } else vistaAcceso();
})(window.TV);
