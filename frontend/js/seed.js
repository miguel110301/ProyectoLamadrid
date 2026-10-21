'use strict';
/* Datos de demostración (ficticios) para poder recorrer reportes sin capturar nada a mano. */
(function (TV) {
  const { ymd, aTs, aMin, pad } = TV.util;

  // Generador pseudoaleatorio determinista: la demo siempre arranca igual
  function mulberry32(a) {
    return function () {
      a |= 0;
      a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const OPERADORES = [
    { nombre: 'Juan Carlos Pérez Hernández', nacimiento: '2002-03-14', expediente: '281045', carrera: 'Comunicación y Periodismo', horarios: [[1, '07:00', '12:00'], [3, '15:00', '21:00']] },
    { nombre: 'María Fernanda López Ruiz', nacimiento: '2001-11-02', expediente: '279318', carrera: 'Diseño y Producción Audiovisual', horarios: [[2, '07:00', '13:00'], [4, '07:00', '13:00']] },
    { nombre: 'Luis Eduardo Ramírez Soto', nacimiento: '2003-07-21', expediente: '290772', carrera: 'Ingeniería de Software', horarios: [[1, '17:00', '21:00'], [3, '17:00', '21:00'], [5, '17:00', '21:00']] },
    { nombre: 'Ana Sofía Martínez Vega', nacimiento: '2000-01-30', expediente: '271904', carrera: 'Ingeniería en Telecomunicaciones y Redes', horarios: [[2, '13:00', '19:00'], [5, '07:00', '13:00']] },
  ];

  const OBSERVACIONES = {
    'corte-cfe': 'Se fue la luz de CFE en el edificio; entró la planta de emergencia.',
    'falla-energia': 'Disparo del UPS de rack principal; se reinició y se verificó la señal.',
    'falla-equipo': 'El servidor de reproducción dejó de responder; se reinició el equipo.',
    'pauta-rtc': 'Se sustituyó la pauta por solicitud de Radio y Televisión de Querétaro.',
    'pauta-ine': 'Se sustituyó la pauta conforme al oficio vigente del INE.',
    'ajuste-prog': 'Se recorrió el bloque de programación por transmisión especial.',
    'falla-programa': 'El videoclip se congeló a mitad de la reproducción; se cargó el respaldo.',
    otro: 'Intermitencia en el enlace de retorno; se notificó a soporte.',
  };

  TV.seed = {
    crear() {
      const rnd = mulberry32(20261013);
      const entre = (a, b) => a + Math.floor(rnd() * (b - a + 1));
      const ahora = new Date();
      const hoy = ymd(ahora);

      const alta = ymd(new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate() - 28));
      const operadores = OPERADORES.map((o, i) => ({
        id: 'op' + (i + 1),
        nombre: o.nombre,
        nacimiento: o.nacimiento,
        expediente: o.expediente,
        carrera: o.carrera,
        huella: true,
        alta,
        versionesHorario: [{ desde: alta, horarios: o.horarios.map(([dia, inicio, fin]) => ({ dia, inicio, fin })) }],
      }));

      const registros = [];
      const incidencias = [];
      const justificaciones = [];

      for (let atras = 28; atras >= 1; atras--) {
        const d = new Date(ahora.getFullYear(), ahora.getMonth(), ahora.getDate() - atras);
        const fecha = ymd(d);
        operadores.forEach((op) => {
          op.versionesHorario[0].horarios
            .filter((h) => h.dia === d.getDay())
            .forEach((h) => {
              const iniTs = aTs(fecha, h.inicio);
              const finTs = aTs(fecha, h.fin);
              const r = rnd();
              let ent = iniTs + entre(-10, 5) * 60000; // a tiempo (hasta 5 min después)
              let sal = finTs + entre(0, 8) * 60000;
              if (r >= 0.65 && r < 0.75) ent = iniTs + entre(6, 10) * 60000; // retardo (5 a 10 min)
              else if (r >= 0.75 && r < 0.82) {
                ent = iniTs + entre(6, 10) * 60000; // retardo + salida temprana (turno incompleto)
                sal = finTs - entre(10, 40) * 60000;
              } else if (r >= 0.82 && r < 0.88) sal = finTs - entre(8, 40) * 60000; // solo salida temprana
              else if (r >= 0.88) {
                // falta: algunas ya justificadas por el administrador
                if (rnd() < 0.4) justificaciones.push({ id: TV.db.uid(), operadorId: op.id, fecha, turnoInicio: h.inicio, concepto: 'Falta', motivo: ['Consulta médica', 'Examen en la facultad', 'Permiso de la coordinación'][entre(0, 2)], creadoTs: finTs + 3600000 });
                if (r >= 0.94) return; // no vino
                ent = iniTs + entre(11, 25) * 60000; // llegó pasados 10 min: se registra su entrada, pero como falta
              }
              registros.push({
                id: TV.db.uid(),
                operadorId: op.id,
                fecha,
                turno: { inicio: h.inicio, fin: h.fin },
                iniTs,
                finTs,
                entradaTs: ent,
                salidaTs: sal,
                salidaAnticipada: sal < finTs - 3 * 60000,
              });

              if (rnd() < 0.18) {
                const tipo = TV.TIPOS[entre(0, TV.TIPOS.length - 1)];
                const mi = aMin(h.inicio) + entre(20, Math.max(21, aMin(h.fin) - aMin(h.inicio) - 20));
                incidencias.push({
                  id: TV.db.uid(),
                  operadorId: op.id,
                  fecha,
                  hora: `${pad(Math.floor(mi / 60))}:${pad(mi % 60)}`,
                  registradoTs: aTs(fecha, `${pad(Math.floor(mi / 60))}:${pad(mi % 60)}`) + entre(1, 12) * 60000,
                  programa: ['Noticiero', 'Barra infantil', 'Cápsulas culturales', 'Deportes UAQ', ''][entre(0, 4)],
                  duracionMin: tipo.duracion ? entre(2, 45) : null,
                  tipo: tipo.id,
                  observacion: OBSERVACIONES[tipo.id],
                });
              }
            });
        });
      }

      return { version: 2, creado: hoy, operadores, registros, incidencias, justificaciones };
    },
  };
})(window.TV);
