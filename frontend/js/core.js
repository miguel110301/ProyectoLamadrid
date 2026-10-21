'use strict';
/*
 * Núcleo compartido: utilidades, almacenamiento y cálculo de asistencia.
 * PROTOTIPO DE INTERFAZ: los datos viven en localStorage del navegador.
 * En la fase de backend, TV.db se sustituye por llamadas al servidor/BD
 * y TV.calc se conserva como especificación de las reglas de negocio.
 */
window.TV = window.TV || {};

(function (TV) {
  const MIN = 60000;

  // Reglas de negocio tomadas de los requerimientos (Anexo 1)
  const CFG = {
    toleranciaRetardoMin: 5, // CLIENTE (2026-10-13): entrada después de 5 min => retardo (el documento original decía 15)
    limiteEntradaMin: 10, // CLIENTE (2026-10-13): después de 10 min es falta; la entrada SÍ se registra (debe cubrir el turno) pero marcada como falta
    toleranciaSalidaMin: 3, // salida hasta 3 min antes => sin advertencia
    anticipoEntradaMin: 60, // SUPUESTO: se puede registrar entrada desde 60 min antes del turno
    reboteSeg: 15, // SUPUESTO: una segunda lectura de la misma persona en menos de 15 s se toma como el mismo toque del dedo
    graciaSinSalidaMin: 120, // SUPUESTO: pasado este margen tras el fin del turno, una entrada sin salida deja de estar vigente
  };

  const DIAS = ['Domingo', 'Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado'];
  const ORDEN_DIAS = [1, 2, 3, 4, 5, 6, 0]; // semana de lunes a domingo

  const TIPOS = [
    { id: 'corte-cfe', nombre: 'Corte de Energía CFE', duracion: true },
    { id: 'falla-energia', nombre: 'Falla en el sistema de Energía interno', duracion: true },
    { id: 'falla-equipo', nombre: 'Falla de equipo', duracion: true },
    { id: 'pauta-rtc', nombre: 'Sustitución de pauta RTC', duracion: false },
    { id: 'pauta-ine', nombre: 'Sustitución de pauta INE', duracion: false },
    { id: 'ajuste-prog', nombre: 'Ajuste de programación', duracion: false },
    { id: 'falla-programa', nombre: 'Falla de programa o videoclip', duracion: true },
    { id: 'otro', nombre: 'Otro', duracion: true },
  ];

  /* ---------- Utilidades ---------- */
  const pad = (n) => String(n).padStart(2, '0');
  const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const parseYmd = (s) => {
    const [y, m, d] = s.split('-').map(Number);
    return new Date(y, m - 1, d);
  };
  const aTs = (fecha, hhmm) => {
    const [y, m, d] = fecha.split('-').map(Number);
    const [h, mi] = hhmm.split(':').map(Number);
    return new Date(y, m - 1, d, h, mi).getTime();
  };
  const aMin = (hhmm) => {
    const [h, m] = hhmm.split(':').map(Number);
    return h * 60 + m;
  };
  const fmtFecha = (s) => {
    const [y, m, d] = s.split('-');
    return `${d}/${m}/${y}`;
  };
  const fmtFechaLarga = (d) =>
    d.toLocaleDateString('es-MX', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  const fmtHora = (ts) => {
    const d = new Date(ts);
    return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  const fmtHoraSeg = (ts) => {
    const d = new Date(ts);
    return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
  };
  const fmtFechaHora = (ts) => `${fmtFecha(ymd(new Date(ts)))} ${fmtHora(ts)}`;
  // "4 h 40 min" (tablas)
  const durCorta = (min) => {
    min = Math.max(0, Math.round(min));
    const h = Math.floor(min / 60);
    const m = min % 60;
    if (!h) return `${m} min`;
    return m ? `${h} h ${m} min` : `${h} h`;
  };
  // "2 horas y 10 minutos" (mensajes al operador)
  const durLarga = (min) => {
    min = Math.max(0, Math.round(min));
    const h = Math.floor(min / 60);
    const m = min % 60;
    const hs = `${h} ${h === 1 ? 'hora' : 'horas'}`;
    const ms = `${m} ${m === 1 ? 'minuto' : 'minutos'}`;
    if (h && m) return `${hs} y ${ms}`;
    return h ? hs : ms;
  };
  const edad = (nacimiento, ref = new Date()) => {
    const n = parseYmd(nacimiento);
    let e = ref.getFullYear() - n.getFullYear();
    const m = ref.getMonth() - n.getMonth();
    if (m < 0 || (m === 0 && ref.getDate() < n.getDate())) e--;
    return e;
  };
  const esc = (v) =>
    String(v ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);
  const tipoNombre = (id) => (TIPOS.find((t) => t.id === id) || { nombre: id }).nombre;

  /* ---------- Almacenamiento (prototipo) ---------- */
  const KEY = 'tvuaq.datos.v1';
  let datos = null;

  const db = {
    get() {
      if (datos) return datos;
      try {
        datos = JSON.parse(localStorage.getItem(KEY));
      } catch (e) {
        datos = null;
      }
      if (!datos || !Array.isArray(datos.operadores)) {
        datos = TV.seed.crear();
        db.guardar();
      }
      datos.justificaciones = datos.justificaciones || [];
      datos.ediciones = datos.ediciones || [];
      datos.ajustes = datos.ajustes || []; // cambios manuales de estatus por turno (el vigente)
      return datos;
    },
    guardar() {
      try {
        localStorage.setItem(KEY, JSON.stringify(datos));
      } catch (e) {
        console.warn('No se pudo guardar en localStorage', e);
      }
    },
    reiniciar() {
      datos = TV.seed.crear();
      db.guardar();
    },
    uid: () => Date.now().toString(36) + Math.random().toString(36).slice(2, 7),
    operador: (id) => db.get().operadores.find((o) => o.id === id),
  };

  /* ---------- Cálculo de asistencia ---------- */
  const calc = {
    // Horario vigente en una fecha: cada modificación crea una versión con fecha de inicio,
    // así cambiar un horario no reescribe las faltas del pasado. Antes del alta no hay turnos.
    horariosEn(op, fecha) {
      let hs = [];
      for (const v of op.versionesHorario) if (v.desde <= fecha) hs = v.horarios;
      return hs;
    },

    // Turnos programados de un operador entre dos fechas (YYYY-MM-DD, inclusivas)
    turnosDe(op, desde, hasta) {
      const out = [];
      const fin = parseYmd(hasta);
      for (let d = parseYmd(desde); d <= fin; d.setDate(d.getDate() + 1)) {
        const fecha = ymd(d);
        calc
          .horariosEn(op, fecha)
          .filter((h) => h.dia === d.getDay())
          .forEach((h) =>
            out.push({
              fecha,
              turno: { inicio: h.inicio, fin: h.fin },
              iniTs: aTs(fecha, h.inicio),
              finTs: aTs(fecha, h.fin),
            })
          );
      }
      return out.sort((a, b) => a.iniTs - b.iniTs);
    },

    // Entrada sin salida que todavía corresponde a un turno en curso
    registroVigente(operadorId, ahora = Date.now()) {
      return db
        .get()
        .registros.find(
          (r) => r.operadorId === operadorId && !r.salidaTs && ahora <= r.finTs + CFG.graciaSinSalidaMin * MIN
        );
    },

    // Turno al que corresponde una entrada hecha ahora (o undefined si no hay)
    turnoParaEntrada(op, ahora = Date.now()) {
      const hoy = ymd(new Date(ahora));
      const registros = db.get().registros;
      return calc
        .turnosDe(op, hoy, hoy)
        .filter(
          (t) =>
            ahora >= t.iniTs - CFG.anticipoEntradaMin * MIN &&
            ahora < t.finTs &&
            !registros.some((r) => r.operadorId === op.id && r.fecha === t.fecha && r.turno.inicio === t.turno.inicio)
        )[0];
    },

    // 'a-tiempo' (hasta 5 min) · 'retardo' (hasta 10 min) · 'falta' (más de 10 min: se registra, pero como falta)
    estadoEntrada(entradaTs, iniTs) {
      if (entradaTs > iniTs + CFG.limiteEntradaMin * MIN) return 'falta';
      return entradaTs > iniTs + CFG.toleranciaRetardoMin * MIN ? 'retardo' : 'a-tiempo';
    },

    /*
     * Resumen de asistencia de un operador en un periodo.
     * Horas en turno = salida - entrada (tal como en los casos 1 y 2 de los requerimientos:
     * 06:50→11:30 son 4 h 40 min, faltan 20 min sobre 5 h programadas).
     * Faltante = max(0, programado - horas en turno). Una falta cuenta su turno completo.
     * Un turno justificado por el administrador deja de contar como falta, retardo, turno
     * incompleto y tiempo faltante, y se cuenta aparte en "justificadas".
     */
    resumen(op, desde, hasta, ahora = Date.now(), { pendientes = false } = {}) {
      const regs = db.get().registros.filter((r) => r.operadorId === op.id && r.fecha >= desde && r.fecha <= hasta);
      const justs = db.get().justificaciones.filter((j) => j.operadorId === op.id);
      const ajustes = db.get().ajustes.filter((x) => x.operadorId === op.id);
      const res = { filas: [], asistencias: 0, faltas: 0, retardos: 0, incompletos: 0, justificadas: 0, sinSalida: 0, faltanteMin: 0 };

      calc.turnosDe(op, desde, hasta).forEach((t) => {
        const prog = (t.finTs - t.iniTs) / MIN;
        const fila = { ...t, programadoMin: prog, entradaTs: null, salidaTs: null, trabajadoMin: 0, faltanteMin: 0, estado: '', retardo: false, faltaTardia: false, incompleto: false, justificada: false, motivo: '', justId: '', editado: false, edicionMotivo: '', ajuste: '' };
        const r = regs.find((x) => x.fecha === t.fecha && x.turno.inicio === t.turno.inicio);
        let completo = false; // tiene entrada y salida

        if (!r) {
          // Sin entrada pasados los minutos límite ya es falta (llegar después también lo sería)
          if (ahora <= t.iniTs + CFG.limiteEntradaMin * MIN) {
            if (!pendientes) return;
            fila.estado = 'pendiente';
          } else {
            fila.estado = 'falta';
            fila.faltanteMin = prog;
          }
        } else {
          fila.entradaTs = r.entradaTs;
          const llegada = calc.estadoEntrada(r.entradaTs, t.iniTs);
          fila.retardo = llegada === 'retardo';
          fila.faltaTardia = llegada === 'falta'; // entró, pero pasado el límite: queda como falta
          if (!r.salidaTs) {
            fila.estado = fila.faltaTardia ? 'falta' : ahora <= t.finTs + CFG.graciaSinSalidaMin * MIN ? 'en-curso' : 'sin-salida';
          } else {
            completo = true;
            fila.salidaTs = r.salidaTs;
            fila.trabajadoMin = Math.round((r.salidaTs - r.entradaTs) / MIN);
            fila.faltanteMin = Math.max(0, prog - fila.trabajadoMin);
            fila.incompleto = fila.retardo && r.salidaTs < t.finTs;
            fila.estado = fila.faltaTardia ? 'falta' : fila.incompleto ? 'incompleto' : fila.retardo ? 'retardo' : 'asistencia';
          }
        }

        // El administrador cambió el estatus a mano (Editar): manda sobre lo que calculó el sensor
        let cuentaAsistencia = completo && !fila.faltaTardia;
        const aj = ajustes.find((x) => x.fecha === t.fecha && x.turnoInicio === t.turno.inicio);
        if (aj) {
          fila.ajuste = aj.estado;
          fila.editado = true;
          fila.edicionMotivo = aj.motivo;
          fila.estado = aj.estado;
          fila.retardo = aj.estado === 'retardo';
          fila.incompleto = false;
          fila.faltaTardia = false;
          fila.faltanteMin = aj.estado === 'falta' ? prog : 0;
          cuentaAsistencia = aj.estado !== 'falta'; // asistencia y retardo cuentan como asistencia
        }

        // Solo se justifica una falta o un retardo (un turno con asistencia normal solo se puede editar)
        const j = justs.find((x) => x.fecha === t.fecha && x.turnoInicio === t.turno.inicio);
        fila.justificable = fila.estado === 'falta' || fila.retardo || fila.incompleto;
        if (j && fila.justificable) {
          fila.justificada = true;
          fila.motivo = j.motivo;
          fila.justId = j.id;
          fila.faltanteMin = 0;
          res.justificadas++;
        }

        if (cuentaAsistencia) res.asistencias++;
        if (fila.estado === 'falta' && !fila.justificada) res.faltas++;
        if (fila.estado === 'sin-salida') res.sinSalida++;
        if (fila.retardo && !fila.justificada) res.retardos++;
        if (fila.incompleto && !fila.justificada) res.incompletos++;
        res.faltanteMin += fila.faltanteMin;
        res.filas.push(fila);
      });
      return res;
    },
  };

  Object.assign(TV, { CFG, DIAS, ORDEN_DIAS, TIPOS, MIN, db, calc, util: { pad, ymd, parseYmd, aTs, aMin, fmtFecha, fmtFechaLarga, fmtHora, fmtHoraSeg, fmtFechaHora, durCorta, durLarga, edad, esc, tipoNombre } });
})(window.TV);
